package com.constructionos.app.core.network

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class NativeAuthenticationResponseTest {
    @Test
    fun authenticatedResponseRequiresBearerToken() {
        val response = NativeAuthenticationResponse(
            status = NativeAuthenticationResponse.STATUS_AUTHENTICATED,
            tokenType = "Bearer",
            accessToken = "opaque-token",
            membershipId = "membership-1",
        )

        assertEquals("opaque-token", response.requireBearerToken())
    }

    @Test
    fun membershipSelectionCannotBeUsedAsSession() {
        val response = NativeAuthenticationResponse(
            status = NativeAuthenticationResponse.STATUS_MEMBERSHIP_SELECTION,
            grantToken = "grant-token",
            memberships = listOf(
                NativeMembershipOption(
                    membershipId = "membership-1",
                    organizationId = "organization-1",
                    organizationName = "Demo Contractor",
                ),
            ),
        )

        assertThrows(IllegalArgumentException::class.java) {
            response.requireBearerToken()
        }
    }
}
