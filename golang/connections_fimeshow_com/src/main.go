package main

import (
	"bufio"
	"context"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/mail"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/antchfx/htmlquery"
	"github.com/chromedp/cdproto/cdp"
	"github.com/chromedp/cdproto/network"
	"github.com/chromedp/chromedp"
	"github.com/gocolly/colly/v2"
)

// Cookie represents the structure of a cookie
type Cookie struct {
	Name           string  `json:"name"`
	Value          string  `json:"value"`
	Domain         string  `json:"domain"`
	Path           string  `json:"path"`
	SameSite       string  `json:"sameSite"`
	Secure         bool    `json:"secure"`
	Session        bool    `json:"session"`
	StoreId        any     `json:"storeId"`
	ExpirationDate float64 `json:"expirationDate"`
	HostOnly       bool    `json:"hostOnly"`
	HttpOnly       bool    `json:"httpOnly"`
}

type Profile struct {
	ProfileName string
	CompanyName string
	Email       string
	LinkedIn    string
}

const targetUrl = "https://connections.fimeshow.com/event/fime-2024-2/people/RXZlbnRWaWV3XzgwNTg1NA==?filters=RmllbGREZWZpbml0aW9uXzY0ODA5OQ%253D%253D%3ARmllbGRWYWx1ZV8yMDgwOTcxOQ%253D%253D%2CRmllbGRWYWx1ZV8yMDgwOTgzMg%253D%253D"

func main() {
	cookieData, err := os.ReadFile("cookies.json")
	if err != nil {
		log.Fatal(err)
	}

	var cookies []Cookie
	err = json.Unmarshal(cookieData, &cookies)
	if err != nil {
		log.Fatal(err)
	}

	options := []chromedp.ExecAllocatorOption{
		chromedp.DisableGPU,
		chromedp.Flag("headless", true),
	}

	// Create a new context
	allocCtx, cancel := chromedp.NewExecAllocator(context.Background(), options...)
	// ensure that the browser process is terminated when done
	defer cancel()

	ctx, cancel := chromedp.NewContext(allocCtx)
	defer cancel()

	// give the browser up to 10 seconds to start
	ctx, cancel = context.WithTimeout(ctx, 10000*time.Second)
	defer cancel()

	err = chromedp.Run(ctx, setCookies(cookies...))
	if err != nil {
		log.Fatal(err)
	}

	file, err := os.Open("profile_urls.txt")
	if err != nil {
		_ = collectAllProfileUrls(ctx)
		time.Sleep(2 * time.Second)
		file, _ = os.Open("profile_urls.txt")
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)

	var urls []string

	for scanner.Scan() {
		urls = append(urls, scanner.Text())
	}

	if err := scanner.Err(); err != nil {
		log.Fatal(err)
	}

	collectProfileInfo(ctx, urls)

	notifyProcessDone()
}

func notifyProcessDone() {
	apiUrl := "https://api.simplepush.io/send"
	data := url.Values{}
	data.Set("key", "nathan123")
	data.Set("title", "Golang Crawling")
	data.Set("msg", "Crawling process is done!")
	data.Set("event", "Event done")

	u, _ := url.ParseRequestURI(apiUrl)
	urlStr := u.String()

	client := &http.Client{}
	r, _ := http.NewRequest(http.MethodPost, urlStr, strings.NewReader(data.Encode()))

	client.Do(r)
}

func collectProfileInfo(ctx context.Context, urls []string) {
	// Navigate each URL
	outputFile, err := os.Open("output.csv")
	if err != nil {
		outputFile, err = os.Create("output.csv")
		if err != nil {
			log.Fatal(err)
		}
	}
	defer outputFile.Close()

	csvWriter := csv.NewWriter(outputFile)
	defer csvWriter.Flush()

	csvWriter.Write([]string{"Contact Name", "Company Name", "Email", "LinkedIn URL"})

	c := colly.NewCollector(
		colly.MaxDepth(2),
	)

	for _, url := range urls[1550:] {
		done := make(chan bool, 1)

		go func(url string, done chan bool) {
			profile := Profile{}

			var body string
			err := chromedp.Run(ctx,
				// TODO: remove hard code
				chromedp.Navigate(url),
				chromedp.WaitVisible(`main div ~ h2`, chromedp.ByQuery),
				chromedp.Text(`main div ~ h2`, &profile.ProfileName, chromedp.ByQuery),
				chromedp.Text(`main h4 ~ h3`, &profile.CompanyName, chromedp.ByQuery),
				chromedp.WaitVisible(`//main//h2[contains(text(), "About me")]`, chromedp.BySearch),
				chromedp.OuterHTML("html", &body),
			)
			if err != nil {
				log.Fatal(err)
			}

			// Use the body variable for parsing or further processing
			processBody(c, body, url, &profile)
			csvWriter.Write([]string{profile.ProfileName, profile.CompanyName, profile.Email, profile.LinkedIn})
			csvWriter.Flush()

			done <- true
		}(url, done)

		select {
		case <-done:
			fmt.Println("Operation finished successfully.")
		case <-time.After(15 * time.Second):
			chromedp.Stop()
			fmt.Println("Operation timed out, moving on.")
		}
	}

	if err = csvWriter.Error(); err != nil {
		log.Fatal(err)
	}
}

func processBody(c *colly.Collector, body string, url string, profile *Profile) {
	// Create a new reader from the string
	reader := strings.NewReader(body)

	// Parse the HTML document
	doc, err := htmlquery.Parse(reader)
	if err != nil {
		log.Fatal(err)
	}

	linkedinAnchor, err := htmlquery.Query(doc, `//a[contains(@href, "linkedin")]`)
	if err != nil || linkedinAnchor == nil {
		log.Default().Printf("LinkedIn not found of %s\n", url)
	} else {
		for _, attr := range linkedinAnchor.Attr {
			if attr.Key == "href" {
				profile.LinkedIn = attr.Val
			}
		}
	}

	websiteAnchor, err := htmlquery.Query(doc, "//h2[text()='Contact details']/../following-sibling::div[1]//a")
	if err != nil || websiteAnchor == nil {
		log.Default().Printf("Contact website not found of %s\n", url)
		return
	} else {
		for _, attr := range websiteAnchor.Attr {
			if attr.Key == "href" {
				email, linkedin := collectInfoFromWebsite(c, attr.Val)
				profile.Email = email
				if profile.LinkedIn == "" {
					profile.LinkedIn = linkedin
				}
				break
			}
		}
	}

}

func collectInfoFromWebsite(c *colly.Collector, url string) (string, string) {
	linkedin := ""
	email := ""

	c.OnHTML("a[href]", func(h *colly.HTMLElement) {
		if strings.Contains(strings.ToLower(h.Attr("href")), "contact") ||
			strings.Contains(strings.ToLower(h.Text), "contact") {
			c.Visit(h.Request.AbsoluteURL(h.Attr("href")))
		}
	})

	c.OnHTML("a[href]", func(e *colly.HTMLElement) {
		link := e.Attr("href")

		// Check for LinkedIn profile links
		if strings.Contains(link, "linkedin.com/") {
			fmt.Printf("LinkedIn profile found: %s\n", link)
			linkedin = link
		}

		// Check for email address in mailto:
		if strings.HasPrefix(link, "mailto:") {
			emailAddress := strings.TrimPrefix(link, "mailto:")
			// You should parse and validate the email address found
			if _, err := mail.ParseAddress(emailAddress); err == nil {
				fmt.Printf("Email found: %s\n", emailAddress)
				if email == "" {
					email = emailAddress
				}
			} else {
				log.Printf("Invalid email format found: %s", emailAddress)
			}
		}
	})

	c.OnRequest(func(r *colly.Request) {
		fmt.Printf("Visited url %s\n", r.URL.String())
	})

	// Error handling
	c.OnError(func(_ *colly.Response, err error) {
		log.Println("Something went wrong:", err)
	})

	err := c.Visit(url)
	if err != nil {
		fmt.Printf("Failed to visit link %s\n", url)
	}

	return email, linkedin
}

func collectAllProfileUrls(ctx context.Context) map[string]bool {
	attendees := []map[string]string{}

	err := chromedp.Run(ctx,
		chromedp.Navigate(targetUrl),
		chromedp.Click("//button//span[contains(text(), 'Accept all')]", chromedp.BySearch),
		chromedp.ActionFunc(func(ctx context.Context) error {
			var previousHeight int64
			scrollCount := 0

			for {
				// Scroll down and wait for loading.
				err := scrollAndWait(ctx)
				if err != nil {
					return err
				}
				scrollCount += 1
				fmt.Printf("Scroll number %d\n", scrollCount)

				// If the indicator is found or loading more doesn't increase document height, we've reached the end.
				var currentHeight int64
				err = chromedp.Evaluate(`document.body.scrollHeight`, &currentHeight).Do(ctx)
				if err == nil && currentHeight == previousHeight {
					break // End of content reached
				}
				previousHeight = currentHeight
			}

			chromedp.AttributesAll(".infinite-scroll-component a", &attendees, chromedp.ByQueryAll).Do(ctx)
			return nil
		}),
	)
	if err != nil {
		log.Fatal(err)
	}

	allProfileLinks := map[string]bool{}
	for _, v := range attendees {
		allProfileLinks[v["href"]] = true
	}

	fmt.Printf("Total items is %d\n", len(allProfileLinks))
	for k := range allProfileLinks {
		fmt.Println(k)
	}

	for {
		file, err := os.Create("profile_urls.txt")
		if err != nil {
			continue
		}
		defer file.Close()

		for k := range allProfileLinks {
			url := fmt.Sprintf("https://connections.fimeshow.com/%s\n", k)
			file.WriteString(url)
		}
		break
	}

	return allProfileLinks
}

func scrollAndWait(ctx context.Context) error {
	// Scroll to bottom
	err := chromedp.Evaluate(`window.scrollTo(0, document.body.scrollHeight);`, nil).Do(ctx)
	if err != nil {
		return err
	}
	// Wait a bit to let the page load
	select {
	case <-time.After(3 * time.Second):
	case <-ctx.Done():
		return ctx.Err()
	}
	return nil
}

func setCookies(cookies ...Cookie) chromedp.Tasks {
	tasks := chromedp.Tasks{}
	for _, cookie := range cookies {
		tasks = append(tasks, chromedp.ActionFunc(func(ctx context.Context) error {
			cookieBuilder := network.SetCookie(cookie.Name, cookie.Value).
				WithDomain(cookie.Domain).
				WithPath(cookie.Path).
				WithSecure(cookie.Secure).
				WithHTTPOnly(cookie.HttpOnly).
				WithSameSite(network.CookieSameSite(cookie.SameSite))

			if cookie.ExpirationDate > 0 {
				sec := int64(cookie.ExpirationDate)
				nsec := int64((cookie.ExpirationDate - float64(sec)) * 1e9)

				timeSinceEpoch := cdp.TimeSinceEpoch(time.Unix(sec, nsec))
				cookieBuilder.WithExpires(&timeSinceEpoch)
			}

			return cookieBuilder.Do(ctx)
		}))
	}
	return tasks
}
