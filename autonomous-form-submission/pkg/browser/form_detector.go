package browser

import (
	"context"
	"fmt"
	"strings"

	"github.com/chromedp/chromedp"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
)

// FormDetector handles detection and analysis of contact forms
type FormDetector struct{}

// NewFormDetector creates a new form detector
func NewFormDetector() *FormDetector {
	return &FormDetector{}
}

// DetectContactForm checks if the current page has a contact form
func (fd *FormDetector) DetectContactForm(ctx context.Context) (*models.ContactForm, error) {
	// Get current page URL for logging
	var currentURL string
	chromedp.Run(ctx, chromedp.Location(&currentURL))
	
	// First, check if there are any forms on the page
	var formCount int
	if err := chromedp.Run(ctx,
		chromedp.Evaluate(`document.querySelectorAll('form').length`, &formCount),
	); err != nil {
		return nil, fmt.Errorf("failed to count forms: %w", err)
	}

	if formCount == 0 {
		fmt.Printf("    ℹ️  No forms found on page: %s\n", currentURL)
		return nil, nil // No forms found
	}

	fmt.Printf("    📝 Found %d form(s) on page: %s\n", formCount, currentURL)

	// Analyze each form to find a contact form
	for i := 0; i < formCount; i++ {
		form, err := fd.analyzeForm(ctx, i)
		if err != nil {
			fmt.Printf("    ⚠️  Form %d: Error analyzing - %v\n", i+1, err)
			continue
		}
		
		if form != nil {
			isContact := fd.isContactForm(form)
			fmt.Printf("    📋 Form %d: %d fields | Email: %v | Message: %v | IsContact: %v\n",
				i+1, len(form.Fields), fd.hasEmailField(form), fd.hasMessageField(form), isContact)
			
			if isContact {
				fmt.Printf("    ✅ Contact form detected (Form %d)\n", i+1)
				return form, nil
			}
		}
	}

	fmt.Printf("    ❌ No contact form found among %d form(s)\n", formCount)
	return nil, nil
}

// Helper methods for detailed logging
func (fd *FormDetector) hasEmailField(form *models.ContactForm) bool {
	for _, field := range form.Fields {
		fieldLower := strings.ToLower(field.Name + field.Placeholder + field.Label)
		if strings.Contains(fieldLower, "email") || strings.Contains(fieldLower, "e-mail") {
			return true
		}
	}
	return false
}

func (fd *FormDetector) hasMessageField(form *models.ContactForm) bool {
	for _, field := range form.Fields {
		fieldLower := strings.ToLower(field.Name + field.Placeholder + field.Label)
		if strings.Contains(fieldLower, "message") || strings.Contains(fieldLower, "comment") ||
		   strings.Contains(fieldLower, "inquiry") || strings.Contains(fieldLower, "question") ||
		   field.Type == "textarea" {
			return true
		}
	}
	return false
}

// analyzeForm extracts information from a specific form
func (fd *FormDetector) analyzeForm(ctx context.Context, formIndex int) (*models.ContactForm, error) {
	script := fmt.Sprintf(`
(function() {
	const form = document.querySelectorAll('form')[%d];
	if (!form) return null;

	function getLabel(element) {
		// Try label[for] attribute first
		if (element.id) {
			const label = form.querySelector('label[for="' + element.id + '"]');
			if (label) return label.textContent.trim();
		}
		
		// Try parent label
		const parentLabel = element.closest('label');
		if (parentLabel) {
			return parentLabel.textContent.replace(element.value || '', '').trim();
		}
		
		// Try aria-label
		if (element.getAttribute('aria-label')) {
			return element.getAttribute('aria-label').trim();
		}
		
		// Try previous sibling text (common pattern: <label>Text</label><input>)
		let prev = element.previousElementSibling;
		if (prev && prev.tagName === 'LABEL') {
			return prev.textContent.trim();
		}
		
		// Try parent's previous sibling (for wrapped inputs)
		const parent = element.parentElement;
		if (parent) {
			const parentPrev = parent.previousElementSibling;
			if (parentPrev && parentPrev.tagName === 'LABEL') {
				return parentPrev.textContent.trim();
			}
		}
		
		return '';
	}

	function generateSelector(element) {
		if (!element) return '';
		if (element.id) return '#' + element.id;
		if (element.name) return '[name="' + element.name + '"]';
		return element.tagName.toLowerCase();
	}

	const inputs = form.querySelectorAll('input, textarea, select');
	const fields = [];

	inputs.forEach(input => {
		if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
			return;
		}

		fields.push({
			name: input.name || input.id || '',
			type: input.type || input.tagName.toLowerCase(),
			placeholder: input.placeholder || '',
			label: getLabel(input),
			required: input.required,
			selector: generateSelector(input)
		});
	});

	const submitButton = form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');

	return {
		fields: fields,
		submitSelector: generateSelector(submitButton),
		formHTML: form.outerHTML.substring(0, 500)
	};
})();
`, formIndex)

	var formData map[string]interface{}
	if err := chromedp.Run(ctx,
		chromedp.Evaluate(script, &formData),
	); err != nil {
		return nil, err
	}

	if formData == nil {
		return nil, nil
	}

	// Convert to ContactForm model
	form := &models.ContactForm{}
	
	if fields, ok := formData["fields"].([]interface{}); ok {
		for _, f := range fields {
			if fieldMap, ok := f.(map[string]interface{}); ok {
				field := models.FormField{
					Name:        getString(fieldMap, "name"),
					Type:        getString(fieldMap, "type"),
					Placeholder: getString(fieldMap, "placeholder"),
					Label:       getString(fieldMap, "label"),
					Required:    getBool(fieldMap, "required"),
					Selector:    getString(fieldMap, "selector"),
				}
				form.Fields = append(form.Fields, field)
			}
		}
	}

	form.SubmitSelector = getString(formData, "submitSelector")
	form.FormHTML = getString(formData, "formHTML")

	return form, nil
}

// isContactForm determines if a form is likely a contact form
func (fd *FormDetector) isContactForm(form *models.ContactForm) bool {
	hasEmail := false
	hasMessage := false
	_ = false // hasName placeholder for future use
	
	// Check for essential contact form fields
	for _, field := range form.Fields {
		fieldLower := strings.ToLower(field.Name + field.Placeholder + field.Label)
		
		if strings.Contains(fieldLower, "email") || strings.Contains(fieldLower, "e-mail") {
			hasEmail = true
		}
		if strings.Contains(fieldLower, "message") || strings.Contains(fieldLower, "comment") ||
		   strings.Contains(fieldLower, "inquiry") || strings.Contains(fieldLower, "question") ||
		   field.Type == "textarea" {
			hasMessage = true
		}
		// hasName check removed for now - can be added later for stricter validation
	}

	// A contact form typically has at least email and message fields
	return hasEmail && hasMessage
}

// DetectCaptcha checks if the page has a CAPTCHA
func (fd *FormDetector) DetectCaptcha(ctx context.Context) (bool, string, error) {
	// Check for various CAPTCHA types
	captchaChecks := map[string]string{
		"recaptcha_v2": `document.querySelector('.g-recaptcha, iframe[src*="recaptcha"]') !== null`,
		"recaptcha_v3": `document.querySelector('[data-sitekey]') !== null || typeof grecaptcha !== 'undefined'`,
		"hcaptcha":     `document.querySelector('.h-captcha, iframe[src*="hcaptcha"]') !== null`,
		"cloudflare":   `document.querySelector('#cf-challenge-running, .cf-browser-verification') !== null`,
		"turnstile":    `document.querySelector('[data-sitekey*="cloudflare"]') !== null`,
	}

	for captchaType, checkScript := range captchaChecks {
		var hasCaptcha bool
		if err := chromedp.Run(ctx,
			chromedp.Evaluate(checkScript, &hasCaptcha),
		); err != nil {
			continue
		}

		if hasCaptcha {
			return true, captchaType, nil
		}
	}

	return false, "", nil
}

// GetCaptchaSiteKey extracts the CAPTCHA site key if present
func (fd *FormDetector) GetCaptchaSiteKey(ctx context.Context, captchaType string) (string, error) {
	var script string
	
	switch captchaType {
	case "recaptcha_v2", "recaptcha_v3":
		script = `
			const element = document.querySelector('[data-sitekey]') || 
			               document.querySelector('.g-recaptcha');
			return element ? element.getAttribute('data-sitekey') : '';
		`
	case "hcaptcha":
		script = `
			const element = document.querySelector('.h-captcha');
			return element ? element.getAttribute('data-sitekey') : '';
		`
	case "turnstile":
		script = `
			const element = document.querySelector('[data-sitekey*="cloudflare"]');
			return element ? element.getAttribute('data-sitekey') : '';
		`
	default:
		return "", nil
	}

	var siteKey string
	if err := chromedp.Run(ctx, chromedp.Evaluate(script, &siteKey)); err != nil {
		return "", err
	}

	return siteKey, nil
}

// IsContactPage checks if the URL or page content indicates a contact page
func IsContactPage(url, title, h1Text string) bool {
	urlLower := strings.ToLower(url)
	titleLower := strings.ToLower(title)
	h1Lower := strings.ToLower(h1Text)

	contactKeywords := []string{
		"contact", "get-in-touch", "reach-us", "support",
		"help", "get-started", "talk-to-us", "reach-out",
	}

	for _, keyword := range contactKeywords {
		if strings.Contains(urlLower, keyword) ||
		   strings.Contains(titleLower, keyword) ||
		   strings.Contains(h1Lower, keyword) {
			return true
		}
	}

	return false
}

// Helper functions
func getString(m map[string]interface{}, key string) string {
	if val, ok := m[key].(string); ok {
		return val
	}
	return ""
}

func getBool(m map[string]interface{}, key string) bool {
	if val, ok := m[key].(bool); ok {
		return val
	}
	return false
}
