package main

import (
	"context"
	"fmt"
	"log"
	"strings"
	"time"

	"github.com/chromedp/chromedp"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/browser"
	"github.com/nhatnguyen/autonomous-form-submission/pkg/models"
)

func main() {
	url := "https://www.avtech.com.au/about-us/contact-us"
	
	fmt.Println("========================================")
	fmt.Println("Form Detection Debug")
	fmt.Println("========================================")
	fmt.Printf("Testing URL: %s\n\n", url)

	// Create fresh browser context
	ctx, cancel := chromedp.NewContext(context.Background())
	defer cancel()

	// Set timeout
	timeoutCtx, timeoutCancel := context.WithTimeout(ctx, 60*time.Second)
	defer timeoutCancel()

	// Navigate to page
	fmt.Println("1. Navigating to page...")
	start := time.Now()
	if err := chromedp.Run(timeoutCtx,
		chromedp.Navigate(url),
		chromedp.WaitReady("body", chromedp.ByQuery),
		chromedp.Sleep(3*time.Second), // Wait for dynamic content
	); err != nil {
		log.Fatalf("Navigation failed: %v", err)
	}
	fmt.Printf("   ✓ Navigation took: %v\n\n", time.Since(start))

	// Check for forms
	fmt.Println("2. Checking for forms...")
	var formCount int
	if err := chromedp.Run(timeoutCtx,
		chromedp.Evaluate(`document.querySelectorAll('form').length`, &formCount),
	); err != nil {
		log.Fatalf("Failed to count forms: %v", err)
	}
	fmt.Printf("   Found %d form(s)\n\n", formCount)

	if formCount == 0 {
		fmt.Println("❌ NO FORMS FOUND - This is the problem!")
		return
	}

	// Get all input fields with details
	var fieldsJSON string
	if err := chromedp.Run(timeoutCtx,
		chromedp.Evaluate(`
			const form = document.querySelector('form');
			if (!form) return '[]';
			
			const inputs = form.querySelectorAll('input, textarea, select');
			const fields = [];
			
			inputs.forEach(input => {
				if (input.type === 'hidden' || input.type === 'submit' || input.type === 'button') {
					return;
				}
				
				// Get label using multiple methods
				let label = '';
				if (input.id) {
					const labelEl = form.querySelector('label[for="' + input.id + '"]');
					if (labelEl) label = labelEl.textContent.trim();
				}
				if (!label) {
					const parent = input.closest('label');
					if (parent) label = parent.textContent.replace(input.value || '', '').trim();
				}
				if (!label && input.getAttribute('aria-label')) {
					label = input.getAttribute('aria-label').trim();
				}
				
				fields.push({
					name: input.name || input.id || '',
					type: input.type || input.tagName.toLowerCase(),
					placeholder: input.placeholder || '',
					label: label,
					required: input.required
				});
			});
			
			return JSON.stringify(fields, null, 2);
		`, &fieldsJSON),
	); err != nil {
		log.Printf("Failed to get fields: %v", err)
	} else {
		fmt.Println("3. Form Fields Detected:")
		fmt.Println(fieldsJSON)
		fmt.Println()
	}

	// Now test the actual detector
	fmt.Println("4. Testing FormDetector...")
	detector := browser.NewFormDetector()
	form, err := detector.DetectContactForm(timeoutCtx)
	if err != nil {
		log.Printf("   ❌ Detector error: %v", err)
	} else if form == nil {
		fmt.Println("   ❌ FormDetector returned nil (no contact form detected)")
		fmt.Println("   This is why it's marked as 'not_found'!")
		
		// Debug why it failed
		fmt.Println("\n5. Debugging why detection failed...")
		var debugResult map[string]bool
		if err := chromedp.Run(timeoutCtx, chromedp.Evaluate(`
			(function() {
				const form = document.querySelector('form');
				if (!form) return {email: false, message: false};
				
				const inputs = form.querySelectorAll('input, textarea');
				let hasEmail = false, hasMessage = false;
				
				inputs.forEach(input => {
					if (input.type === 'hidden' || input.type === 'submit') return;
					
					const text = (input.name || '') + (input.placeholder || '') + (input.id || '');
					const labelEl = form.querySelector('label[for="' + input.id + '"]');
					const labelText = labelEl ? labelEl.textContent.toLowerCase() : '';
					const combined = (text + labelText).toLowerCase();
					
					if (combined.includes('email') || combined.includes('e-mail')) {
						hasEmail = true;
					}
					if (combined.includes('message') || combined.includes('question') || 
					    combined.includes('comment') || combined.includes('inquiry') ||
					    input.tagName === 'TEXTAREA') {
						hasMessage = true;
					}
				});
				
				return {email: hasEmail, message: hasMessage};
			})();
		`, &debugResult)); err == nil {
			fmt.Printf("   Has Email Field: %v\n", debugResult["email"])
			fmt.Printf("   Has Message Field: %v\n", debugResult["message"])
			if !debugResult["email"] {
				fmt.Println("   ⚠️  Missing email field!")
			}
			if !debugResult["message"] {
				fmt.Println("   ⚠️  Missing message/question field!")
			}
		}
	} else {
		fmt.Println("   ✅ FormDetector found a contact form!")
		fmt.Printf("   Fields: %d\n", len(form.Fields))
		fmt.Printf("   Has Email: %v\n", hasEmailField(form))
		fmt.Printf("   Has Message: %v\n", hasMessageField(form))
		fmt.Printf("   Submit Selector: %s\n", form.SubmitSelector)
	}

	fmt.Println("\n========================================")
}

func hasEmailField(form *models.ContactForm) bool {
	for _, field := range form.Fields {
		fieldLower := strings.ToLower(field.Name + field.Placeholder + field.Label)
		if strings.Contains(fieldLower, "email") || strings.Contains(fieldLower, "e-mail") {
			return true
		}
	}
	return false
}

func hasMessageField(form *models.ContactForm) bool {
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
