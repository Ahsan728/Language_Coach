package com.ahsansuny.languagecoach.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.ahsansuny.languagecoach.data.local.entity.LessonEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LessonDao {
    @Query("SELECT * FROM lessons WHERE languageCode = :languageCode ORDER BY remoteId ASC")
    fun observeByLanguage(languageCode: String): Flow<List<LessonEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(lessons: List<LessonEntity>)

    @Query("DELETE FROM lessons WHERE languageCode = :languageCode")
    suspend fun clearLanguage(languageCode: String)
}
