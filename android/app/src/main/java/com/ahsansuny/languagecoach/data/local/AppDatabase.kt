package com.ahsansuny.languagecoach.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.ahsansuny.languagecoach.data.local.dao.LessonDao
import com.ahsansuny.languagecoach.data.local.dao.ProgressSnapshotDao
import com.ahsansuny.languagecoach.data.local.dao.VocabularyDao
import com.ahsansuny.languagecoach.data.local.entity.LessonEntity
import com.ahsansuny.languagecoach.data.local.entity.ProgressSnapshotEntity
import com.ahsansuny.languagecoach.data.local.entity.VocabularyEntity

@Database(
    entities = [LessonEntity::class, VocabularyEntity::class, ProgressSnapshotEntity::class],
    version = 3,
    exportSchema = true,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun lessonDao(): LessonDao
    abstract fun vocabularyDao(): VocabularyDao
    abstract fun progressSnapshotDao(): ProgressSnapshotDao
}
