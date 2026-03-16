package com.ahsansuny.languagecoach.di

import android.content.Context
import androidx.room.Room
import com.ahsansuny.languagecoach.BuildConfig
import com.ahsansuny.languagecoach.data.local.AppDatabase
import com.ahsansuny.languagecoach.data.local.dao.LessonDao
import com.ahsansuny.languagecoach.data.local.dao.ProgressSnapshotDao
import com.ahsansuny.languagecoach.data.local.dao.VocabularyDao
import com.ahsansuny.languagecoach.data.remote.LanguageCoachService
import com.ahsansuny.languagecoach.data.remote.interceptor.BearerAuthInterceptor
import com.ahsansuny.languagecoach.data.remote.interceptor.RequestMetadataInterceptor
import com.ahsansuny.languagecoach.data.repository.LessonRepositoryImpl
import com.ahsansuny.languagecoach.data.repository.ProgressRepositoryImpl
import com.ahsansuny.languagecoach.data.repository.SessionRepositoryImpl
import com.ahsansuny.languagecoach.data.repository.VocabularyRepositoryImpl
import com.ahsansuny.languagecoach.domain.repository.LessonRepository
import com.ahsansuny.languagecoach.domain.repository.ProgressRepository
import com.ahsansuny.languagecoach.domain.repository.SessionRepository
import com.ahsansuny.languagecoach.domain.repository.VocabularyRepository
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import dagger.Binds
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Qualifier
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class IoDispatcher

@Module
@InstallIn(SingletonComponent::class)
object FoundationModule {
    @Provides
    @Singleton
    @IoDispatcher
    fun provideIoDispatcher(): CoroutineDispatcher = Dispatchers.IO

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, "language_coach.db")
            .fallbackToDestructiveMigration()
            .build()

    @Provides
    fun provideLessonDao(database: AppDatabase): LessonDao = database.lessonDao()

    @Provides
    fun provideVocabularyDao(database: AppDatabase): VocabularyDao = database.vocabularyDao()

    @Provides
    fun provideProgressSnapshotDao(database: AppDatabase): ProgressSnapshotDao =
        database.progressSnapshotDao()

    @Provides
    @Singleton
    fun provideBaseUrl(): HttpUrl = BuildConfig.BASE_URL.toHttpUrl()

    @Provides
    @Singleton
    fun provideRequestMetadataInterceptor(): RequestMetadataInterceptor = RequestMetadataInterceptor()

    @Provides
    @Singleton
    fun provideLoggingInterceptor(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.ENABLE_VERBOSE_LOGGING) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.BASIC
            }
        }

    @Provides
    @Singleton
    fun provideOkHttpClient(
        bearerAuthInterceptor: BearerAuthInterceptor,
        requestMetadataInterceptor: RequestMetadataInterceptor,
        loggingInterceptor: HttpLoggingInterceptor,
    ): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(requestMetadataInterceptor)
            .addInterceptor(bearerAuthInterceptor)
            .addInterceptor(loggingInterceptor)
            .build()

    @Provides
    @Singleton
    fun provideMoshi(): Moshi =
        Moshi.Builder()
            .addLast(KotlinJsonAdapterFactory())
            .build()

    @Provides
    @Singleton
    fun provideRetrofit(
        baseUrl: HttpUrl,
        okHttpClient: OkHttpClient,
        moshi: Moshi,
    ): Retrofit =
        Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(MoshiConverterFactory.create(moshi))
            .build()

    @Provides
    @Singleton
    fun provideLanguageCoachService(retrofit: Retrofit): LanguageCoachService =
        retrofit.create(LanguageCoachService::class.java)
}

@Module
@InstallIn(SingletonComponent::class)
abstract class RepositoryModule {
    @Binds
    abstract fun bindSessionRepository(impl: SessionRepositoryImpl): SessionRepository

    @Binds
    abstract fun bindLessonRepository(impl: LessonRepositoryImpl): LessonRepository

    @Binds
    abstract fun bindVocabularyRepository(impl: VocabularyRepositoryImpl): VocabularyRepository

    @Binds
    abstract fun bindProgressRepository(impl: ProgressRepositoryImpl): ProgressRepository
}
