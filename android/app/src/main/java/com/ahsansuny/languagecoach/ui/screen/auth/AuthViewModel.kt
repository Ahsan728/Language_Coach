package com.ahsansuny.languagecoach.ui.screen.auth

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ahsansuny.languagecoach.core.network.ApiResult
import com.ahsansuny.languagecoach.core.network.toDisplayMessage
import com.ahsansuny.languagecoach.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.launch

data class AuthUiState(
    val name: String = "",
    val email: String = "",
    val rememberSession: Boolean = true,
    val isSubmitting: Boolean = false,
    val errorMessage: String? = null,
)

@HiltViewModel
class AuthViewModel @Inject constructor(
    private val sessionRepository: SessionRepository,
) : ViewModel() {
    private val events = MutableSharedFlow<AuthEvent>()
    val uiEvents = events.asSharedFlow()

    var uiState by mutableStateOf(AuthUiState())
        private set

    fun onNameChanged(value: String) {
        uiState = uiState.copy(name = value)
    }

    fun onEmailChanged(value: String) {
        uiState = uiState.copy(email = value, errorMessage = null)
    }

    fun onRememberChanged(value: Boolean) {
        uiState = uiState.copy(rememberSession = value)
    }

    fun submit() {
        if (uiState.isSubmitting) return

        viewModelScope.launch {
            uiState = uiState.copy(isSubmitting = true, errorMessage = null)
            when (
                val result = sessionRepository.signIn(
                    name = uiState.name,
                    email = uiState.email,
                    rememberSession = uiState.rememberSession,
                )
            ) {
                is ApiResult.Success -> {
                    uiState = uiState.copy(isSubmitting = false, errorMessage = null)
                    events.emit(AuthEvent.SignedIn)
                }
                is ApiResult.Failure -> {
                    uiState = uiState.copy(
                        isSubmitting = false,
                        errorMessage = result.error.toDisplayMessage(),
                    )
                }
            }
        }
    }
}

sealed interface AuthEvent {
    data object SignedIn : AuthEvent
}
