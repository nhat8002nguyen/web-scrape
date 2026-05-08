package models

import "time"

type FormField struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Label       string `json:"label"`
	Placeholder string `json:"placeholder"`
	Required    bool   `json:"required"`
	Selector    string `json:"selector"`
}

type ContactForm struct {
	DomainID    int64       `json:"domain_id"`
	URL         string      `json:"url"`
	Fields      []FormField `json:"fields"`
	SubmitSelector string   `json:"submit_selector"`
	HasCaptcha  bool        `json:"has_captcha"`
	CaptchaType string      `json:"captcha_type,omitempty"`
	FormHTML    string      `json:"form_html,omitempty"`
	CreatedAt   time.Time   `json:"created_at"`
}

type FormFieldMapping struct {
	FieldType string   `json:"field_type"` // email, name, message, phone, company, subject
	Selectors []string `json:"selectors"`  // CSS selectors to try
	Keywords  []string `json:"keywords"`   // Keywords in name/id/placeholder
}

var DefaultFieldMappings = []FormFieldMapping{
	{
		FieldType: "email",
		Selectors: []string{
			"input[type='email']",
			"input[name*='email']",
			"input[id*='email']",
			"input[placeholder*='email']",
		},
		Keywords: []string{"email", "e-mail", "mail"},
	},
	{
		FieldType: "name",
		Selectors: []string{
			"input[name*='name']",
			"input[id*='name']",
			"input[placeholder*='name']",
		},
		Keywords: []string{"name", "full name", "your name", "contact name"},
	},
	{
		FieldType: "message",
		Selectors: []string{
			"textarea[name*='message']",
			"textarea[id*='message']",
			"textarea[placeholder*='message']",
			"textarea[name*='comment']",
			"textarea[name*='inquiry']",
		},
		Keywords: []string{"message", "comment", "inquiry", "question", "details"},
	},
	{
		FieldType: "phone",
		Selectors: []string{
			"input[type='tel']",
			"input[name*='phone']",
			"input[id*='phone']",
			"input[placeholder*='phone']",
		},
		Keywords: []string{"phone", "telephone", "tel", "mobile"},
	},
	{
		FieldType: "company",
		Selectors: []string{
			"input[name*='company']",
			"input[id*='company']",
			"input[name*='organization']",
		},
		Keywords: []string{"company", "organization", "business"},
	},
	{
		FieldType: "subject",
		Selectors: []string{
			"input[name*='subject']",
			"input[id*='subject']",
		},
		Keywords: []string{"subject", "topic", "regarding"},
	},
}
