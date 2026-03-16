package com.ahsansuny.languagecoach.domain.repository

import com.ahsansuny.languagecoach.core.model.LanguageCode
import com.ahsansuny.languagecoach.core.model.LessonSummary
import com.ahsansuny.languagecoach.core.model.ProgressSnapshot
import com.ahsansuny.languagecoach.core.model.VocabularyEntry
import com.ahsansuny.languagecoach.core.network.ApiResult
import kotlinx.coroutines.flow.Flow

sealed interface AppSessionState {
    data object Loading : AppSessionState
    data class Authenticated(
        val displayName: String,
        val email: String,
    ) : AppSessionState

    data object Unauthenticated : AppSessionState
}

interface SessionRepository {
    val sessionState: Flow<AppSessionState>

    suspend fun signIn(
        name: String,
        email: String,
        rememberSession: Boolean,
    ): ApiResult<Unit>

    suspend fun signOut()
}

interface LessonRepository {
    fun observeLessons(languageCode: LanguageCode): Flow<List<LessonSummary>>
    suspend fun refreshLessons(languageCode: LanguageCode): ApiResult<Unit>
}

interface VocabularyRepository {
    fun observeVocabulary(languageCode: LanguageCode): Flow<List<VocabularyEntry>>
    suspend fun refreshVocabulary(languageCode: LanguageCode): ApiResult<Unit>
}

interface ProgressRepository {
    fun observeProgress(): Flow<ProgressSnapshot?>
    suspend fun refreshProgress(): ApiResult<Unit>
}
