package com.ahsansuny.languagecoach.data.repository

import com.ahsansuny.languagecoach.core.network.ApiResult
import com.ahsansuny.languagecoach.core.network.safeApiCall
import com.ahsansuny.languagecoach.data.preferences.ActiveSessionStore
import com.ahsansuny.languagecoach.data.remote.LanguageCoachService
import com.ahsansuny.languagecoach.data.remote.dto.CreateSessionRequest
import com.ahsansuny.languagecoach.data.remote.dto.toDomain
import com.ahsansuny.languagecoach.di.IoDispatcher
import com.ahsansuny.languagecoach.domain.repository.AppSessionState
import com.ahsansuny.languagecoach.domain.repository.SessionRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.onStart
import kotlinx.coroutines.withContext

@Singleton
class SessionRepositoryImpl @Inject constructor(
    private val service: LanguageCoachService,
    private val activeSessionStore: ActiveSessionStore,
    @IoDispatcher private val ioDispatcher: CoroutineDispatcher,
) : SessionRepository {
    override val sessionState: Flow<AppSessionState> = activeSessionStore.sessionFlow
        .map { session ->
            session?.let {
                AppSessionState.Authenticated(
                    displayName = it.user.name,
                    email = it.user.email,
                )
            } ?: AppSessionState.Unauthenticated
        }
        .onStart { emit(AppSessionState.Loading) }

    override suspend fun signIn(
        name: String,
        email: String,
        rememberSession: Boolean,
    ): ApiResult<Unit> = withContext(ioDispatcher) {
        safeApiCall {
            val normalizedEmail = email.trim().lowercase()
            require(EMAIL_PATTERN.matches(normalizedEmail)) {
                "Please enter a valid email address."
            }

            val resolvedName = name.trim().ifBlank {
                normalizedEmail.substringBefore('@').replaceFirstChar { firstChar ->
                    firstChar.titlecase()
                }
            }

            val response = service.createSession(
                request = CreateSessionRequest(
                    email = normalizedEmail,
                    name = resolvedName,
                    rememberMe = rememberSession,
                ),
            )
            check(response.ok) { "Mobile auth session creation failed." }
            activeSessionStore.update(
                session = response.toDomain(),
                rememberSession = rememberSession,
            )
        }
    }

    override suspend fun signOut() {
        withContext(ioDispatcher) {
            runCatching { service.deleteSession() }
            activeSessionStore.clear()
        }
    }

    private companion object {
        val EMAIL_PATTERN: Regex = Regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")
    }
}
