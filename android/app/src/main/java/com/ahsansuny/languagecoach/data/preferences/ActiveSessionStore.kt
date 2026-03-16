package com.ahsansuny.languagecoach.data.preferences

import com.ahsansuny.languagecoach.core.model.AuthSession
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

@Singleton
class ActiveSessionStore @Inject constructor(
    private val sessionPreferences: SessionPreferences,
) {
    private val _session = MutableStateFlow(loadPersistedSession())
    val sessionFlow: StateFlow<AuthSession?> = _session.asStateFlow()

    init {
        if (_session.value == null) {
            runBlocking {
                sessionPreferences.clear()
            }
        }
    }

    fun currentSession(): AuthSession? = _session.value

    suspend fun update(session: AuthSession, rememberSession: Boolean) {
        _session.value = session
        if (rememberSession) {
            sessionPreferences.saveRememberedSession(session)
        } else {
            sessionPreferences.clear()
        }
    }

    suspend fun clear() {
        _session.value = null
        sessionPreferences.clear()
    }

    private fun loadPersistedSession(): AuthSession? =
        normalize(
            runBlocking {
                sessionPreferences.storedSessionFlow.first()
            },
        )

    private fun normalize(session: AuthSession?): AuthSession? {
        if (session == null) return null
        val expiresAt = session.expiresAtIso ?: return session
        val isExpired = runCatching {
            Instant.parse(expiresAt).isBefore(Instant.now())
        }.getOrDefault(false)
        return session.takeUnless { isExpired }
    }
}
