"""Framework callbacks shared by Java and Kotlin on the JVM."""

JVM_PROTECTED_NAMES: frozenset[str] = frozenset({
    'onCreate', 'onStart', 'onResume', 'onPause', 'onStop', 'onDestroy',
    'onRestart', 'onCreateView', 'onViewCreated', 'onDestroyView',
    'onSaveInstanceState', 'onRestoreInstanceState', 'onActivityResult',
    'onRequestPermissionsResult', 'onNewIntent', 'onConfigurationChanged',
    'onBackPressed', 'onCreateOptionsMenu', 'onOptionsItemSelected',
    'onPrepareOptionsMenu', 'onAttach', 'onDetach', 'onCreateDialog',
    'onDismiss', 'onCancel', 'onActivityCreated',
    'getItem', 'getCount', 'getItemCount', 'onCreateViewHolder',
    'onBindViewHolder', 'getItemViewType', 'getItemId', 'instantiateItem',
    'destroyItem', 'getPageTitle', 'isViewFromObject', 'onMeasure',
    'onLayout', 'onDraw', 'onSizeChanged', 'onTouchEvent',
    'onInterceptTouchEvent', 'dispatchTouchEvent', 'onAttachedToWindow',
    'onDetachedFromWindow', 'onBind', 'onUnbind', 'onStartCommand',
    'onReceive', 'query', 'insert', 'update', 'delete', 'getType',
    'attachBaseContext', 'hashCode', 'equals', 'toString', 'compareTo',
    'clone', 'finalize', 'run', 'call', 'accept', 'apply', 'test', 'get',
    'invoke', 'onSubscribe', 'onNext', 'onError', 'onComplete',
    'subscribe', 'map', 'flatMap', 'writeToParcel', 'describeContents',
    'readFromParcel', 'writeObject', 'readObject', 'readResolve',
    'writeReplace', 'afterPropertiesSet', 'setUp', 'tearDown',
})
