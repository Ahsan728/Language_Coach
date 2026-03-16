package com.ahsansuny.languagecoach.data.remote.dto

import com.ahsansuny.languagecoach.core.model.LanguageCode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class VocabularyEntryKeyTest {
    @Test
    fun stableVocabularyEntryKey_changesWhenCategoryChanges() {
        val workVerb = VocabularyItemDto(
            word = "trabajar",
            article = null,
            english = "to work",
            bengali = "kaj kora",
            pronunciation = "tra-ba-HAR",
            example = "Quiero trabajar aqui.",
            exampleEn = "I want to work here.",
            exampleBn = "Ami ekhane kaj korte chai.",
            category = "jobs",
        )
        val studyVerb = workVerb.copy(category = "daily_life")

        val jobsKey = stableVocabularyEntryKey(LanguageCode.SPANISH, workVerb)
        val dailyLifeKey = stableVocabularyEntryKey(LanguageCode.SPANISH, studyVerb)

        assertNotEquals(jobsKey, dailyLifeKey)
    }

    @Test
    fun stableVocabularyEntryKey_isDeterministicForSameEntry() {
        val item = VocabularyItemDto(
            word = "travailler",
            article = null,
            english = "to work",
            bengali = "kaj kora",
            pronunciation = "tra-va-yay",
            example = "Je vais travailler demain.",
            exampleEn = "I will work tomorrow.",
            exampleBn = "Ami agami kal kaj korbo.",
            category = "jobs",
        )

        val first = stableVocabularyEntryKey(LanguageCode.FRENCH, item)
        val second = stableVocabularyEntryKey(LanguageCode.FRENCH, item)

        assertEquals(first, second)
    }
}
