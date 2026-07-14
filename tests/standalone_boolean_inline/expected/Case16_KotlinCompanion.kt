package com.test

// Case 16: Kotlin companion object 中的方法
class Case16 {

    companion object {

        fun isPublicCompanion(): Boolean {
            return true
        }
    }

    fun use() {
        if (false) {
            doThing()
        }
        val x = Case16.isPublicCompanion()
    }
}
