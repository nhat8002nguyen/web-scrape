package main

import (
	"net/http"
	"time"
)

func convertCookies(customCookies []Cookie) []*http.Cookie {
	httpCookies := make([]*http.Cookie, 0, len(customCookies))

	for _, customCookie := range customCookies {
		expiration := time.Unix(int64(customCookie.ExpirationDate), 0)
		// The SameSite property requires conversion as well, which is shown below.

		httpCookie := &http.Cookie{
			Name:     customCookie.Name,
			Value:    customCookie.Value,
			Domain:   customCookie.Domain,
			Path:     customCookie.Path,
			Secure:   customCookie.Secure,
			HttpOnly: customCookie.HttpOnly,
			Expires:  expiration,
			// HostOnly is not directly used in the http.Cookie, skip this
		}

		// Handle the SameSite attribute
		switch customCookie.SameSite {
		case "Lax":
			httpCookie.SameSite = http.SameSiteLaxMode
		case "Strict":
			httpCookie.SameSite = http.SameSiteStrictMode
		case "None":
			httpCookie.SameSite = http.SameSiteNoneMode
		}

		httpCookies = append(httpCookies, httpCookie)
	}

	return httpCookies
}
