package com.ahsansuny.languagecoach.core.network

import java.io.IOException
import retrofit2.HttpException

sealed interface ApiResult<out T> {
    data class Success<T>(val value: T) : ApiResult<T>
    data class Failure(val error: ApiError) : ApiResult<Nothing>
}

sealed interface ApiError {
    data class Network(val cause: IOException) : ApiError
    data class Http(val code: Int, val body: String?) : ApiError
    data class Serialization(val cause: Throwable) : ApiError
    data class Unknown(val cause: Throwable) : ApiError
}

suspend fun <T> safeApiCall(block: suspend () -> T): ApiResult<T> =
    try {
        ApiResult.Success(block())
    } catch (exception: HttpException) {
        ApiResult.Failure(ApiError.Http(exception.code(), exception.response()?.errorBody()?.string()))
    } catch (exception: IOException) {
        ApiResult.Failure(ApiError.Network(exception))
    } catch (exception: IllegalArgumentException) {
        ApiResult.Failure(ApiError.Serialization(exception))
    } catch (exception: IllegalStateException) {
        ApiResult.Failure(ApiError.Serialization(exception))
    } catch (exception: Throwable) {
        ApiResult.Failure(ApiError.Unknown(exception))
    }

fun ApiError.toDisplayMessage(): String =
    when (this) {
        is ApiError.Http -> body ?: "The server responded with $code."
        is ApiError.Network -> "Network connection failed. Check your base URL or connectivity."
        is ApiError.Serialization -> "The response shape did not match the current mobile contract."
        is ApiError.Unknown -> cause.message ?: "Something unexpected happened."
    }
