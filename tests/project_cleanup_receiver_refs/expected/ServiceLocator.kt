package com.example

class ServiceLocator {
  companion object {
    fun getInstance() = ServiceLocator()
  }

  fun getActionService() = ActionService()
}
