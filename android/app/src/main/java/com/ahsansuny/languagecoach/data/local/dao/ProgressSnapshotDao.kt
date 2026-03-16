package com.ahsansuny.languagecoach.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.ahsansuny.languagecoach.data.local.entity.ProgressSnapshotEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ProgressSnapshotDao {
    @Query("SELECT * FROM progress_snapshots WHERE ownerKey = :ownerKey LIMIT 1")
    fun observe(ownerKey: String = ProgressSnapshotEntity.SELF_OWNER_KEY): Flow<ProgressSnapshotEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(snapshot: ProgressSnapshotEntity)
}
