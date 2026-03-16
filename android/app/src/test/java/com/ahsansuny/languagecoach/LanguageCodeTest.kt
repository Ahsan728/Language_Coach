package com.ahsansuny.languagecoach

import com.ahsansuny.languagecoach.core.model.LanguageCode
import org.junit.Assert.assertEquals
import org.junit.Test

class LanguageCodeTest {
    @Test
    fun fromApiValue_fallsBackSafely() {
        assertEquals(LanguageCode.SPANISH, LanguageCode.fromApiValue("spanish"))
        assertEquals(LanguageCode.FRENCH, LanguageCode.fromApiValue("unknown"))
    }
}
