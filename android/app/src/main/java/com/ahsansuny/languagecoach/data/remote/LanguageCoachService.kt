package com.ahsansuny.languagecoach.data.remote

import com.ahsansuny.languagecoach.data.remote.dto.AuthSessionResponse
import com.ahsansuny.languagecoach.data.remote.dto.CreateSessionRequest
import com.ahsansuny.languagecoach.data.remote.dto.LanguagesResponse
import com.ahsansuny.languagecoach.data.remote.dto.LessonTouchResponse
import com.ahsansuny.languagecoach.data.remote.dto.LessonsResponse
import com.ahsansuny.languagecoach.data.remote.dto.MeResponse
import com.ahsansuny.languagecoach.data.remote.dto.OkResponse
import com.ahsansuny.languagecoach.data.remote.dto.ProgressResponse
import com.ahsansuny.languagecoach.data.remote.dto.VocabularyResponse
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface LanguageCoachService {
    @POST("api/v1/auth/session")
    suspend fun createSession(
        @Body request: CreateSessionRequest,
    ): AuthSessionResponse

    @GET("api/v1/me")
    suspend fun getMe(): MeResponse

    @DELETE("api/v1/auth/session")
    suspend fun deleteSession(): OkResponse

    @GET("api/v1/languages")
    suspend fun getLanguages(): LanguagesResponse

    @GET("api/v1/languages/{language}/lessons")
    suspend fun getLessons(
        @Path("language") language: String,
    ): LessonsResponse

    @POST("api/v1/languages/{language}/lessons/{lessonId}/touch")
    suspend fun touchLesson(
        @Path("language") language: String,
        @Path("lessonId") lessonId: Int,
    ): LessonTouchResponse

    @GET("api/v1/languages/{language}/vocabulary")
    suspend fun getVocabulary(
        @Path("language") language: String,
        @Query("category") category: String? = null,
        @Query("limit") limit: Int? = null,
        @Query("offset") offset: Int? = null,
    ): VocabularyResponse

    @GET("api/v1/progress")
    suspend fun getProgress(
        @Query("include") include: String? = null,
    ): ProgressResponse
}
