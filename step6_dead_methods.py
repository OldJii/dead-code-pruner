#!/usr/bin/env python3
"""
Step 6: Dead method detection and cleanup (with class hierarchy analysis)

Dead methods:
  - void methods with empty body (may contain comments, blank lines, return;)
  - boolean methods that only return true or false (may contain comments)

Pipeline:
  1. Scan all files: collect dead methods + build reference index (method name → file set)
  2. Build class hierarchy, mark leaf/final class public methods as safe to inline
  3. In-memory index for cross-file reference queries (O(1) lookup)
  4. void dead methods: remove standalone call statements
  5. boolean dead methods: inline calls as true/false
"""
import re, os, sys, time, json
from collections import defaultdict

PROJECT_ROOT = None


def strip_code(line):
    """去除字符串内容和行注释，保留代码结构"""
    result = []
    i = 0
    in_str = False
    str_ch = None
    while i < len(line):
        ch = line[i]
        if not in_str:
            if ch in ('"', "'"):
                in_str = True
                str_ch = ch
                result.append(' ')
            elif line[i:i+2] == '//':
                break
            else:
                result.append(ch)
        else:
            result.append(' ')
            if ch == str_ch and (i == 0 or line[i-1] != '\\'):
                in_str = False
        i += 1
    return ''.join(result)


def brace_delta(line):
    clean = strip_code(line)
    return clean.count('{') - clean.count('}')


def is_dead_void_body(body_lines):
    for line in body_lines:
        stripped = line.strip()
        if stripped == '' or stripped == 'return;' or stripped == 'return':
            continue
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or stripped == '*/':
            continue
        return False
    return True


def is_dead_boolean_body(body_lines):
    value = None
    for line in body_lines:
        stripped = line.strip()
        if stripped == '' or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or stripped == '*/':
            continue
        if stripped == 'return true;' or stripped == 'return true':
            if value is not None:
                return None
            value = 'true'
        elif stripped == 'return false;' or stripped == 'return false':
            if value is not None:
                return None
            value = 'false'
        else:
            return None
    return value


SKIP_MODIFIERS = {'abstract', 'open', 'native', 'override'}


def scan_dead_methods(lines, is_kotlin=False):
    """扫描文件中所有可见性的死方法"""
    results = []
    # 用栈追踪嵌套类，正确恢复外层类名
    class_stack = []  # [(class_name, brace_depth_at_open)]
    brace_depth = 0
    current_class = None
    i = 0
    while i < len(lines):
        line = lines[i]
        clean = strip_code(line)

        # 更新大括号深度（跳过字符串和注释中的大括号）
        for ch in clean:
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth -= 1
                # 检查是否关闭了当前内层类
                if class_stack and brace_depth <= class_stack[-1][1]:
                    class_stack.pop()
                    current_class = class_stack[-1][0] if class_stack else None

        class_m = re.search(r'\b(?:class|interface|enum|object)\s+(\w+)', clean)
        if class_m and '{' in clean:
            cls_name = class_m.group(1)
            class_stack.append((cls_name, brace_depth - 1))
            current_class = cls_name

        if is_kotlin:
            m = re.search(r'\bfun\s+(\w+)\s*\(', clean)
        else:
            m = re.search(r'\b(void|boolean|Boolean)\s+(\w+)\s*\(', clean)

        if not m:
            i += 1
            continue

        if is_kotlin:
            method_name = m.group(1)
            return_type = None
        else:
            return_type = m.group(1)
            method_name = m.group(2)

        # 收集注解和修饰符
        decl_start = i
        annotations = set()
        modifiers = set()
        hit_content = False
        for k in range(i - 1, max(i - 8, -1), -1):
            prev = lines[k].strip()
            if prev == '':
                if hit_content:
                    break
                continue
            hit_content = True
            if prev.startswith('@'):
                ann_match = re.match(r'@([\w.]+)', prev)
                if ann_match:
                    full_name = ann_match.group(1)
                    annotations.add(full_name.split('.')[-1])
                    annotations.add(full_name)
                decl_start = k
            elif prev.endswith('{') or prev.endswith('}') or prev.endswith(';'):
                break
            elif re.match(r'^(public|private|protected|static|final|abstract|override|open|synchronized|native)\b', prev):
                for mod in re.findall(r'\b(abstract|open|override|native)\b', prev):
                    modifiers.add(mod)
                decl_start = k
            elif prev.startswith('//') or prev.startswith('/*') or prev.startswith('*') or prev == '*/':
                decl_start = k
            else:
                break

        for mod in re.findall(r'\b(abstract|open|override|native)\b', clean):
            modifiers.add(mod)

        if any(skip in method_name for skip in _SKIP_METHOD_PATTERNS):
            i += 1
            continue

        # 跳过有任何注解的方法
        if annotations:
            i += 1
            continue

        if modifiers & SKIP_MODIFIERS:
            i += 1
            continue

        # 判断是否可以安全内联调用（private 或 static 方法无虚方法调度问题）
        all_mods = set(re.findall(r'\b(public|private|protected|static|final|synchronized|native)\b', clean))
        for k_prev in range(i - 1, max(i - 3, -1), -1):
            p = lines[k_prev].strip()
            if p == '' or p.startswith('@') or p.startswith('//') or p.startswith('*'):
                break
            if p.endswith(';') or p.endswith('{') or p.endswith('}'):
                break
            for md in re.findall(r'\b(public|private|protected|static|final)\b', p):
                all_mods.add(md)
            break
        safe_to_inline = ('private' in all_mods or 'static' in all_mods)

        # 提取参数数量
        sig_text = clean[m.end():]
        # 合并多行签名
        j_sig = i
        while ')' not in sig_text and j_sig < min(i + 5, len(lines) - 1):
            j_sig += 1
            sig_text += ' ' + strip_code(lines[j_sig])
        paren_content = ''
        if ')' in sig_text:
            paren_content = sig_text[:sig_text.index(')')].strip()
        param_count = 0 if paren_content == '' else paren_content.count(',') + 1

        # Kotlin 表达式体
        if is_kotlin and '{' not in clean:
            expr_m = re.search(r'=\s*(\w+)\s*$', clean)
            if expr_m:
                expr_val = expr_m.group(1)
                if expr_val == 'Unit':
                    results.append({
                        'name': method_name, 'kind': 'void', 'value': None,
                        'decl_start': decl_start, 'decl_end': i, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })
                elif expr_val in ('true', 'false'):
                    results.append({
                        'name': method_name, 'kind': 'boolean', 'value': expr_val,
                        'decl_start': decl_start, 'decl_end': i, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })
            i += 1
            continue

        # 找方法体
        if '{' not in clean:
            j = i + 1
            while j < len(lines) and '{' not in strip_code(lines[j]):
                j += 1
            if j >= len(lines):
                i += 1
                continue
            open_brace_line = j
        else:
            open_brace_line = i

        bc = 0
        found = False
        end_line = open_brace_line
        for j in range(open_brace_line, len(lines)):
            delta = brace_delta(lines[j])
            bc += delta
            if bc > 0:
                found = True
            if found and bc <= 0:
                end_line = j
                break

        if not found:
            i += 1
            continue

        body_start = open_brace_line
        body_end = end_line

        if '{' in strip_code(lines[body_start]):
            after_brace = strip_code(lines[body_start]).split('{', 1)[1].strip()
            if after_brace and after_brace != '}':
                body_content = [after_brace.rstrip('}').strip()]
            else:
                body_content = [lines[j] for j in range(body_start + 1, body_end)]
        else:
            body_content = [lines[j] for j in range(body_start + 1, body_end)]

        if is_kotlin:
            sig = ' '.join(lines[j] for j in range(i, open_brace_line + 1))
            has_bool_return = re.search(r':\s*Boolean\b', sig)
            if has_bool_return:
                val = is_dead_boolean_body(body_content)
                if val is not None:
                    results.append({
                        'name': method_name, 'kind': 'boolean', 'value': val,
                        'decl_start': decl_start, 'decl_end': end_line, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })
            else:
                if is_dead_void_body(body_content):
                    results.append({
                        'name': method_name, 'kind': 'void', 'value': None,
                        'decl_start': decl_start, 'decl_end': end_line, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })
        else:
            if return_type == 'void':
                if is_dead_void_body(body_content):
                    results.append({
                        'name': method_name, 'kind': 'void', 'value': None,
                        'decl_start': decl_start, 'decl_end': end_line, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })
            elif return_type in ('boolean', 'Boolean'):
                val = is_dead_boolean_body(body_content)
                if val is not None:
                    results.append({
                        'name': method_name, 'kind': 'boolean', 'value': val,
                        'decl_start': decl_start, 'decl_end': end_line, 'class_name': current_class,
                        'param_count': param_count, 'safe_to_inline': safe_to_inline, 'all_mods': all_mods
                    })

        i = end_line + 1

    return results


def build_ref_index(all_files, progress_cb=None):
    """一次遍历所有文件，构建 {方法名 -> set(文件路径)} 引用索引（含 :: 方法引用）"""
    METHOD_CALL_PAT = re.compile(r'\b(\w+)\s*\(')
    METHOD_REF_PAT = re.compile(r'::(\w+)\b')
    ref_index = defaultdict(set)
    for i, fpath in enumerate(all_files):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        for m in METHOD_CALL_PAT.finditer(content):
            name = m.group(1)
            if len(name) > 2:
                ref_index[name].add(fpath)
        for m in METHOD_REF_PAT.finditer(content):
            name = m.group(1)
            if len(name) > 2:
                ref_index[name].add(fpath)
        if progress_cb and (i + 1) % 2000 == 0:
            progress_cb(i + 1)
    return ref_index


FRAMEWORK_PREFIXES = ('Abs', 'Base', 'Abstract', 'I')

def is_framework_class(class_name):
    """判断类名是否为框架扩展点（不应清理其模板方法）"""
    if not class_name:
        return True
    if class_name.startswith('Abstract') or class_name.endswith('Base'):
        return True
    if class_name.startswith('Abs') and len(class_name) > 3 and class_name[3].isupper():
        return True
    if class_name.startswith('Base') and len(class_name) > 4 and class_name[4].isupper():
        return True
    if class_name.startswith('I') and len(class_name) > 1 and class_name[1].isupper():
        return True
    return False


def build_class_hierarchy(all_files):
    """构建类继承树：{parent -> set(children)}, final classes, interface/abstract/enum classes, implements classes"""
    children_map = defaultdict(set)
    final_classes = set()
    interface_abstract_enum = set()
    implements_interface = set()

    CLASS_EXTENDS = re.compile(r'\b(?:class|object)\s+(\w+)\s+(?:extends|:)\s+(\w+)')
    FINAL_CLASS = re.compile(r'\bfinal\s+class\s+(\w+)')
    INTERFACE_ABSTRACT = re.compile(r'\b(?:interface|abstract\s+class)\s+(\w+)')
    ENUM_CLASS = re.compile(r'\benum\s+(\w+)')
    CLASS_IMPLEMENTS = re.compile(r'\bclass\s+(\w+)[^{]*\bimplements\s+')

    for fpath in all_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            continue
        for m in CLASS_EXTENDS.finditer(content):
            child, parent = m.group(1), m.group(2)
            children_map[parent].add(child)
        for m in FINAL_CLASS.finditer(content):
            final_classes.add(m.group(1))
        for m in INTERFACE_ABSTRACT.finditer(content):
            interface_abstract_enum.add(m.group(1))
        for m in ENUM_CLASS.finditer(content):
            interface_abstract_enum.add(m.group(1))
        for m in CLASS_IMPLEMENTS.finditer(content):
            implements_interface.add(m.group(1))

    return children_map, final_classes, interface_abstract_enum, implements_interface


def enhance_safe_to_inline(all_dead, children_map, final_classes, interface_abstract_enum, implements_interface=None):
    """基于类继承树，增强 safe_to_inline 标记"""
    if implements_interface is None:
        implements_interface = set()
    enhanced = 0
    for dm in all_dead:
        if dm.get('safe_to_inline'):
            continue
        cls = dm.get('class_name')
        if not cls:
            continue
        if is_framework_class(cls):
            continue
        if cls in interface_abstract_enum:
            continue
        if cls in implements_interface:
            continue
        is_final = cls in final_classes
        has_children = cls in children_map and len(children_map[cls]) > 0
        if is_final or not has_children:
            dm['safe_to_inline'] = True
            dm['enhanced_reason'] = 'final' if is_final else 'leaf'
            enhanced += 1
    return enhanced


def find_refs_from_index(ref_index, method_name, source_file):
    """从内存索引查找引用文件（排除源文件自身）"""
    refs = ref_index.get(method_name, set())
    src_abs = os.path.abspath(source_file)
    return [f for f in refs if os.path.abspath(f) != src_abs]


def remove_void_calls_in_file(filepath, method_name, class_name=None, cross_file=False, param_count=0):
    """在指定文件中删除 void 方法调用"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')

    changed = False
    new_lines = []

    if cross_file and class_name:
        qualifiers = [re.escape(class_name) + r'\s*\.\s*']
    else:
        qualifiers = [r'', r'this\s*\.\s*']
        if class_name:
            qualifiers.append(re.escape(class_name) + r'\s*\.\s*')
    qual_pat = '|'.join(f'(?:{q})' for q in qualifiers)
    # 无参方法只匹配空括号，有参方法匹配任意括号内容
    # Java 必须以分号结尾（排除链式调用如 method().subscribe(...)）
    # Kotlin 无分号，用行末 + 下一行不以 . 开头来排除链式调用
    is_kotlin = filepath.endswith('.kt')
    args_pat = r'\s*\(\s*\)' if param_count == 0 else r'\s*\([^)]*\)'
    line_end_pat = r'\s*;?\s*$' if is_kotlin else r'\s*;\s*$'
    pat = re.compile(
        r'^\s*(?:' + qual_pat + r')' + re.escape(method_name) + args_pat + line_end_pat
    )

    for idx, line in enumerate(lines):
        match_line = line if param_count == 0 else strip_code(line)
        if pat.match(match_line.rstrip()):
            # Kotlin 无分号时，检查下一行是否是链式调用（以 . 开头）
            if is_kotlin and not line.rstrip().endswith(';'):
                next_idx = idx + 1
                if next_idx < len(lines) and lines[next_idx].lstrip().startswith('.'):
                    new_lines.append(line)
                    continue
            changed = True
            continue
        new_lines.append(line)

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
    return changed


def _count_args(text):
    """计算括号内的参数个数"""
    text = text.strip()
    if not text:
        return 0
    depth = 0
    count = 1
    for ch in text:
        if ch in ('(', '['):
            depth += 1
        elif ch in (')', ']'):
            depth -= 1
        elif ch == ',' and depth == 0:
            count += 1
    return count


def _replace_method_call_with_value(line, method_name, value, qual_pat, param_count=0):
    """替换方法调用为常量值，正确处理括号匹配，验证参数数量"""
    pat = re.compile(r'(?<!\w)(?<!\.)(?:' + qual_pat + r')' + re.escape(method_name) + r'\s*\(')
    result = line
    safety = 0
    while safety < 20:
        safety += 1
        m = pat.search(result)
        if not m:
            break
        start = m.start()
        paren_start = result.index('(', m.end() - 1)
        depth = 1
        j = paren_start + 1
        while j < len(result) and depth > 0:
            ch = result[j]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch in ('"', "'"):
                j += 1
                while j < len(result) and result[j] != ch:
                    if result[j] == '\\':
                        j += 1
                    j += 1
            j += 1
        if depth != 0:
            break
        paren_end = j
        # 验证参数数量
        args_text = result[paren_start + 1:paren_end - 1]
        actual_args = _count_args(args_text)
        if actual_args != param_count:
            break
        result = result[:start] + value + result[paren_end:]
    return result


def inline_boolean_calls_in_file(filepath, method_name, value, class_name=None, skip_range=None, cross_file=False, param_count=0):
    """在指定文件中将 boolean 方法调用内联为常量"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')

    if cross_file and class_name:
        qualifiers = [re.escape(class_name) + r'\s*\.\s*']
    else:
        qualifiers = [r'(?:this\s*\.\s*)?']
        if class_name:
            qualifiers.append(re.escape(class_name) + r'\s*\.\s*')
    qual_pat = '|'.join(qualifiers)

    name_pat = re.compile(r'(?<!\w)(?<!\.)(?:' + qual_pat + r')' + re.escape(method_name) + r'\s*\(')

    changed = False
    new_lines = []

    _NOT_TYPE_KW = {'return', 'throw', 'new', 'if', 'while', 'for', 'switch', 'case',
                     'catch', 'else', 'assert', 'yield', 'super', 'this'}

    for i, line in enumerate(lines):
        if skip_range and skip_range[0] <= i <= skip_range[1]:
            new_lines.append(line)
            continue
        clean = strip_code(line)
        # 跳过方法声明行（返回类型 + 方法名），但不跳过 return/throw 等关键字
        decl_m = re.search(r'\b(\w+)\s+' + re.escape(method_name) + r'\s*\(', clean)
        if decl_m and decl_m.group(1) not in _NOT_TYPE_KW:
            new_lines.append(line)
            continue
        m = name_pat.search(clean)
        if m:
            new_line = _replace_method_call_with_value(line, method_name, value, qual_pat, param_count)
            if new_line != line:
                changed = True
                # 仅删除独立的 true;/false; 语句（必须有分号，排除多行表达式中间部分）
                stripped = new_line.strip()
                if re.match(r'^(true|false)\s*;$', stripped):
                    continue
                new_lines.append(new_line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines))
    return changed


def _has_remaining_refs(lines, method_name, decl_start, decl_end, param_count=0):
    """检查文件中在声明范围外是否还有匹配参数数量的方法引用（含 :: 方法引用）"""
    if param_count == 0:
        pat = re.compile(r'\b' + re.escape(method_name) + r'\s*\(\s*\)')
    else:
        pat = re.compile(r'\b' + re.escape(method_name) + r'\s*\(')
    method_ref_pat = re.compile(r'::' + re.escape(method_name) + r'\b')
    for i, line in enumerate(lines):
        if decl_start <= i <= decl_end:
            continue
        clean = strip_code(line)
        if re.search(r'\b(void|boolean|Boolean|fun)\s+' + re.escape(method_name) + r'\s*\(', clean):
            continue
        if method_ref_pat.search(clean):
            return True
        check_line = line if param_count == 0 else clean
        if pat.search(check_line):
            return True
    return False


def delete_method_definitions(filepath, dead_methods):
    """删除文件中的死方法定义（仅当没有残留引用时）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = content.split('\n')
    is_kotlin = filepath.endswith('.kt')

    current_dead = scan_dead_methods(lines, is_kotlin)
    ranges_to_del = []
    for dm in current_dead:
        if any(d['name'] == dm['name'] and d['kind'] == dm['kind']
               and d.get('param_count', 0) == dm.get('param_count', 0) for d in dead_methods):
            if _has_remaining_refs(lines, dm['name'], dm['decl_start'], dm['decl_end'], dm.get('param_count', 0)):
                continue
            ranges_to_del.append((dm['decl_start'], dm['decl_end']))

    if not ranges_to_del:
        return False

    ranges_to_del.sort()
    merged = [ranges_to_del[0]]
    for s, e in ranges_to_del[1:]:
        if s <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))

    deleted = False
    for s, e in reversed(merged):
        bc = sum(brace_delta(lines[j]) for j in range(s, e + 1))
        if bc != 0:
            continue
        del lines[s:e + 1]
        deleted = True

    # 清理连续空行
    final = []
    prev_blank = False
    for line in lines:
        is_blank = line.strip() == ''
        if is_blank and prev_blank:
            continue
        final.append(line)
        prev_blank = is_blank

    if deleted:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(final))
    return deleted


DEFAULT_SKIP_DIRS = {'.git', '.gradle', '.idea', 'build', 'node_modules',
                     '.cursor', 'docs', 'gradle', '.cxx', 'generated', '__pycache__'}

_SKIP_DIR_PATTERNS = set()
_SKIP_METHOD_PATTERNS = set()
_EXTRA_SKIP_DIRS = set()


def load_config(config_path=None):
    """Load step6 config from pruner config file."""
    global _SKIP_DIR_PATTERNS, _SKIP_METHOD_PATTERNS, _EXTRA_SKIP_DIRS
    if not config_path:
        return
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        if config_path.endswith(('.yaml', '.yml')):
            import yaml
            config = yaml.safe_load(content)
        else:
            config = json.loads(content)

        step6_conf = config.get('dead_methods', {})
        _SKIP_METHOD_PATTERNS = set(step6_conf.get('skip_method_patterns', []))
        _SKIP_DIR_PATTERNS = set(step6_conf.get('skip_dir_patterns', []))
        _EXTRA_SKIP_DIRS = set(step6_conf.get('skip_dirs', []))
    except Exception:
        pass


def collect_all_files(dir_path):
    """Collect all Java/Kotlin files (excluding build and configured directories)."""
    skip_dirs = DEFAULT_SKIP_DIRS | _EXTRA_SKIP_DIRS
    all_files = []
    for root, dirs, files in os.walk(dir_path):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        if _SKIP_DIR_PATTERNS:
            skip = False
            for pat in _SKIP_DIR_PATTERNS:
                if pat in root:
                    skip = True
                    break
            if skip:
                continue
        for fname in sorted(files):
            if not (fname.endswith('.java') or fname.endswith('.kt')):
                continue
            all_files.append(os.path.join(root, fname))
    return all_files


def process_project(project_root, dry_run=False):
    """处理整个项目"""
    global PROJECT_ROOT
    PROJECT_ROOT = os.path.abspath(project_root)
    t0 = time.time()

    print("Phase 1: 扫描文件 + 构建引用索引...", flush=True)
    all_files = collect_all_files(project_root)
    print(f"  共 {len(all_files)} 个文件", flush=True)

    # 一次遍历：收集死方法 + 构建引用索引
    all_dead = []
    scanned = 0
    for fpath in all_files:
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            continue
        lines = content.split('\n')
        is_kotlin = fpath.endswith('.kt')
        dead = scan_dead_methods(lines, is_kotlin)
        for dm in dead:
            dm['filepath'] = fpath
            all_dead.append(dm)
        scanned += 1
        if scanned % 2000 == 0:
            print(f"  已扫描 {scanned}/{len(all_files)} 文件，找到 {len(all_dead)} 个死方法", flush=True)

    print(f"  扫描完成: {scanned} 文件，{len(all_dead)} 个死方法 ({time.time()-t0:.1f}s)", flush=True)

    # 构建引用索引
    print("  构建引用索引...", flush=True)
    ref_index = build_ref_index(all_files,
                                 progress_cb=lambda n: print(f"  索引进度: {n}/{len(all_files)}", flush=True))
    print(f"Phase 1 完成 ({time.time()-t0:.1f}s)", flush=True)

    # 构建类继承树 + 增强 safe_to_inline
    print(f"\n  构建类继承树...", flush=True)
    children_map, final_classes, interface_abstract_enum, implements_interface = build_class_hierarchy(all_files)
    enhanced = enhance_safe_to_inline(all_dead, children_map, final_classes, interface_abstract_enum, implements_interface)
    safe_count = sum(1 for dm in all_dead if dm.get('safe_to_inline'))
    print(f"  继承树增强: {enhanced} 个叶子类/final类方法提升为可安全处理 (总可处理: {safe_count})", flush=True)

    if dry_run:
        for dm in all_dead:
            rel = os.path.relpath(dm['filepath'], project_root) if PROJECT_ROOT else os.path.basename(dm['filepath'])
            short = rel
            reason = dm.get('enhanced_reason', '')
            tag = f" [{reason}]" if reason else ""
            safe_tag = " [SAFE]" if dm.get('safe_to_inline') else ""
            print(f"  {dm['kind']} {dm['class_name']}.{dm['name']}  -> {dm.get('value', 'empty')}  [{short}]{safe_tag}{tag}")
        print(f"\n总计 {len(all_dead)} 个死方法 (可安全处理: {safe_count})")
        return

    print(f"\nPhase 2: 处理调用...", flush=True)
    processed = 0
    files_modified = set()

    for dm in all_dead:
        name = dm['name']
        kind = dm['kind']
        value = dm['value']
        cls = dm.get('class_name')
        src = dm['filepath']
        pc = dm.get('param_count', 0)
        safe = dm.get('safe_to_inline', False)

        # 只有 private/static 方法才安全替换/删除调用（无虚方法调度问题）
        if not safe:
            processed += 1
            if processed % 200 == 0:
                print(f"  已处理 {processed}/{len(all_dead)} 个死方法 ({time.time()-t0:.1f}s)", flush=True)
            continue

        # 跨文件：只处理类名限定的调用（如 ClassName.method()）
        if cls:
            ref_files = find_refs_from_index(ref_index, name, src)
            for ref_file in ref_files:
                try:
                    if kind == 'void':
                        if remove_void_calls_in_file(ref_file, name, class_name=cls, cross_file=True, param_count=pc):
                            files_modified.add(ref_file)
                    elif kind == 'boolean':
                        if inline_boolean_calls_in_file(ref_file, name, value, class_name=cls, cross_file=True, param_count=pc):
                            files_modified.add(ref_file)
                except Exception as e:
                    print(f"  WARN: {ref_file}: {e}")

        # 处理源文件中的调用（自引用）
        try:
            if kind == 'void':
                if remove_void_calls_in_file(src, name, class_name=cls, param_count=pc):
                    files_modified.add(src)
            elif kind == 'boolean':
                if inline_boolean_calls_in_file(src, name, value, class_name=cls,
                                                 skip_range=(dm['decl_start'], dm['decl_end']), param_count=pc):
                    files_modified.add(src)
        except Exception as e:
            print(f"  WARN: {src}: {e}")

        processed += 1
        if processed % 200 == 0:
            print(f"  已处理 {processed}/{len(all_dead)} 个死方法 ({time.time()-t0:.1f}s)", flush=True)

    print(f"Phase 2 完成: {processed} 个调用处理，修改了 {len(files_modified)} 个文件 ({time.time()-t0:.1f}s)", flush=True)

    # 刷新被修改文件的索引（Phase 2 替换调用后，原引用可能已不存在）
    if files_modified:
        print(f"\n刷新 {len(files_modified)} 个已修改文件的引用索引...", flush=True)
        METHOD_CALL_PAT = re.compile(r'\b(\w+)\s*\(')
        METHOD_REF_PAT = re.compile(r'::(\w+)\b')
        for fpath in files_modified:
            for name_set in ref_index.values():
                name_set.discard(fpath)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                for m in METHOD_CALL_PAT.finditer(content):
                    name = m.group(1)
                    if len(name) > 2:
                        ref_index[name].add(fpath)
                for m in METHOD_REF_PAT.finditer(content):
                    name = m.group(1)
                    if len(name) > 2:
                        ref_index[name].add(fpath)
            except Exception:
                pass
        print(f"索引刷新完成 ({time.time()-t0:.1f}s)", flush=True)

    # Phase 2 后完整重建引用索引，确保 Phase 3 的引用检查基于最新文件内容
    print(f"\n重建引用索引（确保 Phase 3 准确性）...", flush=True)
    ref_index = build_ref_index(all_files)
    print(f"引用索引重建完成 ({time.time()-t0:.1f}s)", flush=True)

    print(f"\nPhase 3: 删除死方法定义...", flush=True)
    by_file = defaultdict(list)
    for dm in all_dead:
        by_file[dm['filepath']].append(dm)

    del_count = 0
    skip_count = 0
    skip_non_private = 0
    for fpath, methods in by_file.items():
        safe_methods = []
        for dm in methods:
            if not dm.get('safe_to_inline', False):
                skip_non_private += 1
                continue
            mods = dm.get('all_mods', set())
            # private 方法不可能被跨文件调用，跳过跨文件引用检查
            if 'private' in mods:
                safe_methods.append(dm)
                continue
            ref_files = find_refs_from_index(ref_index, dm['name'], fpath)
            if ref_files:
                if 'static' in mods and dm.get('class_name'):
                    qualified_pat = re.compile(
                        re.escape(dm['class_name']) + r'\s*\.\s*' + re.escape(dm['name']) + r'\s*\(')
                    method_ref_pat = re.compile(
                        r'::' + re.escape(dm['name']) + r'\b')
                    unqualified_call_pat = re.compile(
                        r'(?<!\w)(?<!\.)' + re.escape(dm['name']) + r'\s*\(')
                    decl_pat = re.compile(
                        r'\b\w+\s+' + re.escape(dm['name']) + r'\s*\(')
                    has_real_ref = False
                    for rf in ref_files:
                        try:
                            with open(rf, 'r', encoding='utf-8') as f2:
                                content = f2.read()
                                if qualified_pat.search(content):
                                    has_real_ref = True
                                    break
                                if method_ref_pat.search(content):
                                    has_real_ref = True
                                    break
                                for line in content.split('\n'):
                                    sline = strip_code(line)
                                    if unqualified_call_pat.search(sline) and not decl_pat.search(sline):
                                        has_real_ref = True
                                        break
                                if has_real_ref:
                                    break
                        except Exception:
                            has_real_ref = True
                            break
                    if has_real_ref:
                        skip_count += 1
                    else:
                        safe_methods.append(dm)
                else:
                    skip_count += 1
            else:
                safe_methods.append(dm)
        if not safe_methods:
            continue
        try:
            if delete_method_definitions(fpath, safe_methods):
                files_modified.add(fpath)
                del_count += len(safe_methods)
        except Exception as e:
            print(f"  WARN: {fpath}: {e}")
    if skip_non_private:
        print(f"  跳过 {skip_non_private} 个非 private/static 方法", flush=True)
    if skip_count:
        print(f"  跳过 {skip_count} 个有跨文件引用的方法", flush=True)

    print(f"Phase 3 完成: 删除了 {del_count} 个方法定义 ({time.time()-t0:.1f}s)", flush=True)
    print(f"\n总计: 修改了 {len(files_modified)} 个文件, 耗时 {time.time()-t0:.1f}s", flush=True)


def process_single_file(filepath, dry_run=False):
    """处理单个文件（用于测试）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    is_kotlin = filepath.endswith('.kt')

    dead_methods = scan_dead_methods(lines, is_kotlin)
    if not dead_methods:
        return 0, []

    details = []

    for dm in dead_methods:
        name = dm['name']
        kind = dm['kind']
        value = dm['value']
        cls = dm.get('class_name')
        pc = dm.get('param_count', 0)
        safe = dm.get('safe_to_inline', False)

        if not safe:
            continue

        if kind == 'void':
            remove_void_calls_in_file(filepath, name, class_name=cls, param_count=pc)
            details.append(f"  void {name}: calls removed")
        elif kind == 'boolean':
            inline_boolean_calls_in_file(filepath, name, value, class_name=cls,
                                          skip_range=(dm['decl_start'], dm['decl_end']), param_count=pc)
            details.append(f"  boolean {name}={value}: calls inlined")

    if delete_method_definitions(filepath, dead_methods):
        for dm in dead_methods:
            details.append(f"  DEL {dm['kind']} {dm['name']}")

    return len(dead_methods), details


def main():
    dry_run = '--dry-run' in sys.argv
    config_path = None
    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--dry-run':
            i += 1; continue
        if sys.argv[i] == '--config' and i + 1 < len(sys.argv):
            config_path = sys.argv[i + 1]
            i += 2; continue
        args.append(sys.argv[i])
        i += 1

    if not args:
        print("Usage: step6_dead_methods.py <file_or_dir> [--dry-run] [--config pruner.yaml]")
        return

    if not config_path:
        for candidate in ['pruner.yaml', 'pruner.yml', 'pruner.json']:
            if os.path.exists(candidate):
                config_path = candidate
                break
            p = os.path.join(os.path.dirname(os.path.abspath(__file__)), candidate)
            if os.path.exists(p):
                config_path = p
                break

    load_config(config_path)

    target = args[0]

    if os.path.isfile(target):
        count, details = process_single_file(target, dry_run=dry_run)
        print(f"Processed: {count} dead methods")
        for d in details:
            print(d)
    elif os.path.isdir(target):
        process_project(target, dry_run=dry_run)
    else:
        print(f"Error: {target} not found")


if __name__ == '__main__':
    main()
