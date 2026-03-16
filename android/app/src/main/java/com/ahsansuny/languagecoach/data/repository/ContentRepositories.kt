package com.ahsansuny.languagecoach.data.repository

import com.ahsansuny.languagecoach.core.model.LanguageCode
import com.ahsansuny.languagecoach.core.model.LessonSummary
import com.ahsansuny.languagecoach.core.model.ProgressSnapshot
import com.ahsansuny.languagecoach.core.model.VocabularyEntry
import com.ahsansuny.languagecoach.core.network.ApiResult
import com.ahsansuny.languagecoach.core.network.safeApiCall
import com.ahsansuny.languagecoach.data.local.dao.LessonDao
import com.ahsansuny.languagecoach.data.local.dao.ProgressSnapshotDao
import com.ahsansuny.languagecoach.data.local.dao.VocabularyDao
import com.ahsansuny.languagecoach.data.local.entity.toDomain
import com.ahsansuny.languagecoach.data.remote.LanguageCoachService
import com.ahsansuny.languagecoach.data.remote.dto.toEntity
import com.ahsansuny.languagecoach.di.IoDispatcher
import com.ahsansuny.languagecoach.domain.repository.LessonRepository
import com.ahsansuny.languagecoach.domain.repository.ProgressRepository
import com.ahsansuny.languagecoach.domain.repository.VocabularyRepository
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext

@Singleton
class LessonRepositoryImpl @Inject constructor(
    private val lessonDao: LessonDao,
    private val service: LanguageCoachService,
    @IoDispatcher private val ioDispatcher: CoroutineDispatcher,
) : LessonRepository {
    override fun observeLessons(languageCode: LanguageCode): Flow<List<LessonSummary>> =
        lessonDao.observeByLanguage(languageCode.apiValue)
            .map { lessons -> lessons.map { it.toDomain() } }

    override suspend fun refreshLessons(languageCode: LanguageCode): ApiResult<Unit> =
        withContext(ioDispatcher) {
            safeApiCall {
                val remoteLessons = service.getLessons(languageCode.apiValue).lessons
                lessonDao.clearLanguage(languageCode.apiValue)
                lessonDao.upsertAll(remoteLessons.map { it.toEntity(languageCode) })
            }
        }
}

@Singleton
class VocabularyRepositoryImpl @Inject constructor(
    private val vocabularyDao: VocabularyDao,
    private val service: LanguageCoachService,
    @IoDispatcher private val ioDispatcher: CoroutineDispatcher,
) : VocabularyRepository {
    override fun observeVocabulary(languageCode: LanguageCode): Flow<List<VocabularyEntry>> =
        vocabularyDao.observeByLanguage(languageCode.apiValue)
            .map { entries -> entries.map { it.toDomain() } }

    override suspend fun refreshVocabulary(languageCode: LanguageCode): ApiResult<Unit> =
        withContext(ioDispatcher) {
            safeApiCall {
                val remoteEntries = service.getVocabulary(languageCode.apiValue).items
                vocabularyDao.clearLanguage(languageCode.apiValue)
                vocabularyDao.upsertAll(remoteEntries.map { it.toEntity(languageCode) })
            }
        }
}

@Singleton
class ProgressRepositoryImpl @Inject constructor(
    private val progressSnapshotDao: ProgressSnapshotDao,
    private val service: LanguageCoachService,
    @IoDispatcher private val ioDispatcher: CoroutineDispatcher,
) : ProgressRepository {
    override fun observeProgress(): Flow<ProgressSnapshot?> =
        progressSnapshotDao.observe().map { snapshot -> snapshot?.toDomain() }

    override suspend fun refreshProgress(): ApiResult<Unit> =
        withContext(ioDispatcher) {
            safeApiCall {
                val remoteSnapshot = service.getProgress(include = "summary,lessons")
                progressSnapshotDao.upsert(remoteSnapshot.toEntity())
            }
        }
}
