package com.test

class Case4_Kotlin {

    // Case 4.5: override 空方法 → 不删
    override fun onResume() {
    }

    // Case 4.6: 有实际逻辑 → 不删
    private fun realLogic() {
        println("real")
    }

    fun caller() {
        val a = true
        val b = false
        onResume()
        realLogic()
    }
}
