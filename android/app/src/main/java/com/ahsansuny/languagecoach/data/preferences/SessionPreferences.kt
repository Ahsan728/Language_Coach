package com.ahsansuny.languagecoach.data.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.ahsansuny.languagecoach.core.model.AuthSession
import com.ahsansuny.languagecoach.core.model.AuthenticatedUser
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map

private val Context.sessionDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "language_coach_session",
)

@Singleton
class SessionPreferences @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    private object Keys {
        val accessToken = stringPreferencesKey("access_token")
        val tokenType = stringPreferencesKey("token_type")
        val expiresAt = stringPreferencesKey("expires_at")
        val authMode = stringPreferencesKey("auth_mode")
        val userId = longPreferencesKey("user_id")
        val userName = stringPreferencesKey("user_name")
        val userEmail = stringPreferencesKey("user_email")
        val userCreatedAt = stringPreferencesKey("user_created_at")
        val userLastLogin = stringPreferencesKey("user_last_login")
    }

    val storedSessionFlow: Flow<AuthSession?> = context.sessionDataStore.data
        .catch { emit(emptyPreferences()) }
        .map { preferences ->
            val accessToken = preferences[Keys.accessToken] ?: return@map null
            val tokenType = preferences[Keys.tokenType] ?: "Bearer"
            val authMode = preferences[Keys.authMode] ?: "email_only_unverified"
            val userId = preferences[Keys.userId] ?: return@map null
            val userName = preferences[Keys.userName] ?: return@map null
            val userEmail = preferences[Keys.userEmail] ?: return@map null

            AuthSession(
                accessToken = accessToken,
                tokenType = tokenType,
                expiresAtIso = preferences[Keys.expiresAt],
                authMode = authMode,
                user = AuthenticatedUser(
                    id = userId,
                    name = userName,
                    email = userEmail,
                    createdAtIso = preferences[Keys.userCreatedAt],
                    lastLoginIso = preferences[Keys.userLastLogin],
                ),
            )
        }

    suspend fun saveRememberedSession(session: AuthSession) {
        context.sessionDataStore.edit { preferences ->
            preferences[Keys.accessToken] = session.accessToken
            preferences[Keys.tokenType] = session.tokenType
            if (session.expiresAtIso != null) {
                preferences[Keys.expiresAt] = session.expiresAtIso
            } else {
                preferences.remove(Keys.expiresAt)
            }
            preferences[Keys.authMode] = session.authMode
            preferences[Keys.userId] = session.user.id
            preferences[Keys.userName] = session.user.name
            preferences[Keys.userEmail] = session.user.email
            if (session.user.createdAtIso != null) {
                preferences[Keys.userCreatedAt] = session.user.createdAtIso
            } else {
                preferences.remove(Keys.userCreatedAt)
            }
            if (session.user.lastLoginIso != null) {
                preferences[Keys.userLastLogin] = session.user.lastLoginIso
            } else {
                preferences.remove(Keys.userLastLogin)
            }
        }
    }

    suspend fun clear() {
        context.sessionDataStore.edit { preferences ->
            preferences.clear()
        }
    }
}
