package com.ahsansuny.languagecoach.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ahsansuny.languagecoach.domain.repository.AppSessionState
import com.ahsansuny.languagecoach.domain.repository.SessionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

@HiltViewModel
class AppStateViewModel @Inject constructor(
    private val sessionRepository: SessionRepository,
) : ViewModel() {
    val sessionState: StateFlow<AppSessionState> = sessionRepository.sessionState.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = AppSessionState.Loading,
    )

    fun signOut() {
        viewModelScope.launch {
            sessionRepository.signOut()
        }
    }
}
