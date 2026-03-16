package com.ahsansuny.languagecoach.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.ahsansuny.languagecoach.data.local.entity.VocabularyEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface VocabularyDao {
    @Query("SELECT * FROM vocabulary WHERE languageCode = :languageCode ORDER BY category ASC, word ASC, english ASC")
    fun observeByLanguage(languageCode: String): Flow<List<VocabularyEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(entries: List<VocabularyEntity>)

    @Query("DELETE FROM vocabulary WHERE languageCode = :languageCode")
    suspend fun clearLanguage(languageCode: String)
}
