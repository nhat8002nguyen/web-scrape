package captcha

import (
	"context"
	"fmt"
	"strings"

	"github.com/chromedp/chromedp"
)

// CaptchaType represents different CAPTCHA types
type CaptchaType string

const (
	CaptchaTypeNone            CaptchaType = "none"
	CaptchaTypeReCaptchaV2     CaptchaType = "recaptcha_v2_checkbox"
	CaptchaTypeReCaptchaV2Inv  CaptchaType = "recaptcha_v2_invisible"
	CaptchaTypeReCaptchaV3     CaptchaType = "recaptcha_v3"
	CaptchaTypeHCaptcha        CaptchaType = "hcaptcha"
	CaptchaTypeTurnstile       CaptchaType = "cloudflare_turnstile"
	CaptchaTypeUnknown         CaptchaType = "unknown"
)

// CaptchaInfo contains detected CAPTCHA information
type CaptchaInfo struct {
	Type    CaptchaType
	SiteKey string
	URL     string
	Action  string // For reCAPTCHA v3
}

// Detector handles CAPTCHA detection on web pages
type Detector struct{}

// NewDetector creates a new CAPTCHA detector
func NewDetector() *Detector {
	return &Detector{}
}

// Detect identifies if a CAPTCHA is present and what type
func (d *Detector) Detect(ctx context.Context) (*CaptchaInfo, error) {
	// Check for reCAPTCHA v2 (checkbox)
	if info, err := d.detectReCaptchaV2(ctx); err == nil && info != nil {
		return info, nil
	}

	// Check for reCAPTCHA v3
	if info, err := d.detectReCaptchaV3(ctx); err == nil && info != nil {
		return info, nil
	}

	// Check for hCaptcha
	if info, err := d.detectHCaptcha(ctx); err == nil && info != nil {
		return info, nil
	}

	// Check for Cloudflare Turnstile
	if info, err := d.detectCloudflare(ctx); err == nil && info != nil {
		return info, nil
	}

	return &CaptchaInfo{Type: CaptchaTypeNone}, nil
}

func (d *Detector) detectReCaptchaV2(ctx context.Context) (*CaptchaInfo, error) {
	script := `
(function() {
	// Check for visible reCAPTCHA v2 checkbox
	const recaptchaDiv = document.querySelector('.g-recaptcha');
	const recaptchaIframe = document.querySelector('iframe[src*="recaptcha/api2/anchor"]');
	
	if (recaptchaDiv || recaptchaIframe) {
		const siteKey = recaptchaDiv ? 
			recaptchaDiv.getAttribute('data-sitekey') : 
			new URL(recaptchaIframe.src).searchParams.get('k');
		
		return {
			found: true,
			siteKey: siteKey,
			invisible: false
		};
	}
	
	// Check for invisible reCAPTCHA
	const invisibleRecaptcha = document.querySelector('[data-callback][data-sitekey]');
	if (invisibleRecaptcha) {
		return {
			found: true,
			siteKey: invisibleRecaptcha.getAttribute('data-sitekey'),
			invisible: true
		};
	}
	
	return {found: false};
})();
`

	var result map[string]interface{}
	if err := chromedp.Run(ctx, chromedp.Evaluate(script, &result)); err != nil {
		return nil, err
	}

	if found, ok := result["found"].(bool); ok && found {
		siteKey, _ := result["siteKey"].(string)
		invisible, _ := result["invisible"].(bool)
		
		captchaType := CaptchaTypeReCaptchaV2
		if invisible {
			captchaType = CaptchaTypeReCaptchaV2Inv
		}
		
		var url string
		chromedp.Run(ctx, chromedp.Location(&url))
		
		return &CaptchaInfo{
			Type:    captchaType,
			SiteKey: siteKey,
			URL:     url,
		}, nil
	}

	return nil, nil
}

func (d *Detector) detectReCaptchaV3(ctx context.Context) (*CaptchaInfo, error) {
	script := `
(function() {
	// Check for reCAPTCHA v3 (no visible widget)
	if (typeof grecaptcha !== 'undefined' && grecaptcha.enterprise) {
		// Look for site key in page source or hidden elements
		const scripts = Array.from(document.querySelectorAll('script'));
		for (const script of scripts) {
			if (script.textContent.includes('grecaptcha.execute')) {
				const match = script.textContent.match(/execute\(['"]([^'"]+)['"]/);
				if (match) {
					return {
						found: true,
						siteKey: match[1]
					};
				}
			}
		}
	}
	
	return {found: false};
})();
`

	var result map[string]interface{}
	if err := chromedp.Run(ctx, chromedp.Evaluate(script, &result)); err != nil {
		return nil, err
	}

	if found, ok := result["found"].(bool); ok && found {
		siteKey, _ := result["siteKey"].(string)
		var url string
		chromedp.Run(ctx, chromedp.Location(&url))
		
		return &CaptchaInfo{
			Type:    CaptchaTypeReCaptchaV3,
			SiteKey: siteKey,
			URL:     url,
		}, nil
	}

	return nil, nil
}

func (d *Detector) detectHCaptcha(ctx context.Context) (*CaptchaInfo, error) {
	script := `
(function() {
	const hcaptcha = document.querySelector('.h-captcha');
	const hcaptchaIframe = document.querySelector('iframe[src*="hcaptcha.com"]');
	
	if (hcaptcha || hcaptchaIframe) {
		const siteKey = hcaptcha ? 
			hcaptcha.getAttribute('data-sitekey') : 
			'';
		
		return {
			found: true,
			siteKey: siteKey
		};
	}
	
	return {found: false};
})();
`

	var result map[string]interface{}
	if err := chromedp.Run(ctx, chromedp.Evaluate(script, &result)); err != nil {
		return nil, err
	}

	if found, ok := result["found"].(bool); ok && found {
		siteKey, _ := result["siteKey"].(string)
		var url string
		chromedp.Run(ctx, chromedp.Location(&url))
		
		return &CaptchaInfo{
			Type:    CaptchaTypeHCaptcha,
			SiteKey: siteKey,
			URL:     url,
		}, nil
	}

	return nil, nil
}

func (d *Detector) detectCloudflare(ctx context.Context) (*CaptchaInfo, error) {
	script := `
(function() {
	// Check for Cloudflare Turnstile
	const turnstile = document.querySelector('[data-sitekey*="0x"]');
	const cfChallenge = document.querySelector('#cf-challenge-running, .cf-browser-verification');
	
	if (turnstile) {
		return {
			found: true,
			siteKey: turnstile.getAttribute('data-sitekey')
		};
	}
	
	if (cfChallenge) {
		return {
			found: true,
			siteKey: ''
		};
	}
	
	return {found: false};
})();
`

	var result map[string]interface{}
	if err := chromedp.Run(ctx, chromedp.Evaluate(script, &result)); err != nil {
		return nil, err
	}

	if found, ok := result["found"].(bool); ok && found {
		siteKey, _ := result["siteKey"].(string)
		var url string
		chromedp.Run(ctx, chromedp.Location(&url))
		
		return &CaptchaInfo{
			Type:    CaptchaTypeTurnstile,
			SiteKey: siteKey,
			URL:     url,
		}, nil
	}

	return nil, nil
}

// IsSupported checks if the CAPTCHA type is supported for solving
func (d *Detector) IsSupported(captchaType CaptchaType, allowedTypes []string) bool {
	typeStr := string(captchaType)
	
	for _, allowed := range allowedTypes {
		if strings.EqualFold(typeStr, allowed) {
			return true
		}
	}
	
	return false
}

// GetCost returns the estimated cost to solve this CAPTCHA type
func (d *Detector) GetCost(captchaType CaptchaType) float64 {
	costs := map[CaptchaType]float64{
		CaptchaTypeReCaptchaV2:    0.0012, // $0.0012 per solve
		CaptchaTypeReCaptchaV2Inv: 0.0012,
		CaptchaTypeReCaptchaV3:    0.0015,
		CaptchaTypeHCaptcha:       0.0020,
		CaptchaTypeTurnstile:      0.0030,
	}
	
	if cost, ok := costs[captchaType]; ok {
		return cost
	}
	
	return 0.0050 // Default unknown cost
}

// FormatForLog returns a human-readable string for logging
func (info *CaptchaInfo) FormatForLog() string {
	if info.Type == CaptchaTypeNone {
		return "No CAPTCHA detected"
	}
	
	return fmt.Sprintf("CAPTCHA: %s (sitekey: %s)", info.Type, info.SiteKey)
}

// IsSupported checks if this CAPTCHA type is in the allowed list
func (info *CaptchaInfo) IsSupported(allowedTypes []string) bool {
	typeStr := string(info.Type)
	
	for _, allowed := range allowedTypes {
		if strings.EqualFold(typeStr, allowed) {
			return true
		}
	}
	
	return false
}

// GetCost returns the estimated cost to solve this CAPTCHA
func (info *CaptchaInfo) GetCost() float64 {
	costs := map[CaptchaType]float64{
		CaptchaTypeReCaptchaV2:    0.0012,
		CaptchaTypeReCaptchaV2Inv: 0.0012,
		CaptchaTypeReCaptchaV3:    0.0015,
		CaptchaTypeHCaptcha:       0.0020,
		CaptchaTypeTurnstile:      0.0030,
	}
	
	if cost, ok := costs[info.Type]; ok {
		return cost
	}
	
	return 0.0050
}

// PageURL returns the URL field (for compatibility)
func (info *CaptchaInfo) PageURL() string {
	return info.URL
}

// IsInvisible returns true if this is an invisible reCAPTCHA
func (info *CaptchaInfo) IsInvisible() bool {
	return info.Type == CaptchaTypeReCaptchaV2Inv
}
