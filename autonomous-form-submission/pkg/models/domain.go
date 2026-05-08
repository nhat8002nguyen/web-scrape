package models

import "time"

type DomainStatus string

const (
	DomainStatusPending    DomainStatus = "pending"
	DomainStatusDiscovery  DomainStatus = "discovery"
	DomainStatusFound      DomainStatus = "found"
	DomainStatusNotFound   DomainStatus = "not_found"
	DomainStatusFailed     DomainStatus = "failed"
)

type Domain struct {
	ID          int64        `json:"id"`
	URL         string       `json:"url"`
	Status      DomainStatus `json:"status"`
	ContactURL  string       `json:"contact_url,omitempty"`
	CreatedAt   time.Time    `json:"created_at"`
	UpdatedAt   time.Time    `json:"updated_at"`
	Attempts    int          `json:"attempts"`
	LastError   string       `json:"last_error,omitempty"`
}

type DiscoveryTask struct {
	DomainID  int64     `json:"domain_id"`
	URL       string    `json:"url"`
	Depth     int       `json:"depth"`
	CreatedAt time.Time `json:"created_at"`
}
