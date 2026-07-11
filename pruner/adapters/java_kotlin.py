"""Java / Kotlin language adapter.

Covers Android (Activity / Fragment / RecyclerView / ViewPager lifecycle),
Spring / Jakarta EE server frameworks, Dagger / Hilt DI, and standard JVM
conventions (Serializable, Comparable, Runnable, etc.).
"""

from __future__ import annotations

from .base import BaseAdapter

_PROTECTED_NAMES: frozenset[str] = frozenset({
    # ── Android Activity / Fragment lifecycle ──
    'onCreate', 'onStart', 'onResume', 'onPause', 'onStop', 'onDestroy',
    'onRestart', 'onCreateView', 'onViewCreated', 'onDestroyView',
    'onSaveInstanceState', 'onRestoreInstanceState', 'onActivityResult',
    'onRequestPermissionsResult', 'onNewIntent', 'onConfigurationChanged',
    'onBackPressed', 'onCreateOptionsMenu', 'onOptionsItemSelected',
    'onPrepareOptionsMenu', 'onAttach', 'onDetach', 'onCreateDialog',
    'onDismiss', 'onCancel', 'onActivityCreated',

    # ── Android View / Adapter ──
    'getItem', 'getCount', 'getItemCount', 'onCreateViewHolder',
    'onBindViewHolder', 'getItemViewType', 'getItemId',
    'instantiateItem', 'destroyItem', 'getPageTitle', 'isViewFromObject',
    'onMeasure', 'onLayout', 'onDraw', 'onSizeChanged',
    'onTouchEvent', 'onInterceptTouchEvent', 'dispatchTouchEvent',
    'onAttachedToWindow', 'onDetachedFromWindow',

    # ── Android Service / BroadcastReceiver / ContentProvider ──
    'onBind', 'onUnbind', 'onStartCommand', 'onReceive',
    'query', 'insert', 'update', 'delete', 'getType',

    # ── Android Application ──
    'attachBaseContext',

    # ── JVM standard ──
    'hashCode', 'equals', 'toString', 'compareTo', 'clone', 'finalize',
    'run', 'call', 'accept', 'apply', 'test', 'get', 'invoke',

    # ── Reactive / RxJava / Coroutines ──
    'onSubscribe', 'onNext', 'onError', 'onComplete',
    'subscribe', 'map', 'flatMap',

    # ── Serializable / Parcelable ──
    'writeToParcel', 'describeContents', 'readFromParcel',
    'writeObject', 'readObject', 'readResolve', 'writeReplace',

    # ── Spring / Jakarta ──
    'afterPropertiesSet',

    # ── Testing ──
    'setUp', 'tearDown',
})

_PROTECTED_ANNOTATION_PREFIXES: frozenset[str] = frozenset({
    '@Override', '@Bean', '@Component', '@Service', '@Repository',
    '@Controller', '@RestController', '@Configuration',
    '@Autowired', '@Inject', '@PostConstruct', '@PreDestroy',
    '@Test', '@Before', '@After', '@BeforeEach', '@AfterEach',
    '@Provides', '@Binds', '@BindsInstance', '@Module',
    '@Subcomponent', '@JvmStatic', '@JvmOverloads',
    '@OnClick', '@Subscribe', '@EventHandler',
    '@GET', '@POST', '@PUT', '@DELETE', '@PATCH',
    '@RequestMapping', '@GetMapping', '@PostMapping',
    '@Composable', '@Preview',
})


class JavaKotlinAdapter(BaseAdapter):

    @property
    def protected_names(self) -> frozenset[str]:
        return _PROTECTED_NAMES

    @property
    def protected_annotation_prefixes(self) -> frozenset[str]:
        return _PROTECTED_ANNOTATION_PREFIXES

    def is_entry_point(self, record: dict) -> bool:
        name = record.get('name', '')
        if name in self.protected_names:
            return True
        if name == 'main' and 'static' in record.get('all_mods', set()):
            return True
        mods = record.get('all_mods', set())
        if 'override' in mods or 'Override' in mods:
            return True
        return False

    def compute_safe_to_inline(self, record: dict) -> bool:
        if self.is_entry_point(record):
            return False
        mods = record.get('all_mods', set())
        return 'private' in mods or 'static' in mods
