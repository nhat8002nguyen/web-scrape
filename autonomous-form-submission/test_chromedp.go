package main

import (
	"context"
	"fmt"
	"time"

	"github.com/chromedp/chromedp"
)

func main() {
	fmt.Println("========================================")
	fmt.Println("Testing chromedp basic navigation")
	fmt.Println("========================================\n")

	// Test 1: Basic chromedp with default context
	fmt.Println("Test 1: Basic chromedp navigation...")
	ctx, cancel := chromedp.NewContext(context.Background())
	defer cancel()

	start := time.Now()

	var title string
	err := chromedp.Run(ctx,
		chromedp.Navigate("https://example.com"),
		chromedp.Sleep(2*time.Second),
		chromedp.Title(&title),
	)

	duration := time.Since(start)

	fmt.Printf("  Duration: %v\n", duration)
	fmt.Printf("  Error: %v\n", err)
	fmt.Printf("  Title: %s\n", title)

	if err != nil && duration < time.Second {
		fmt.Println("  ❌ FAILED TOO FAST - Context issue\n")
	} else if err != nil {
		fmt.Println("  ❌ FAILED with error\n")
	} else {
		fmt.Println("  ✅ SUCCESS\n")
	}

	// Test 2: With explicit timeout
	fmt.Println("Test 2: With 30-second timeout...")
	ctx2, cancel2 := chromedp.NewContext(context.Background())
	defer cancel2()

	timeoutCtx, timeoutCancel := context.WithTimeout(ctx2, 30*time.Second)
	defer timeoutCancel()

	start2 := time.Now()

	var title2 string
	err2 := chromedp.Run(timeoutCtx,
		chromedp.Navigate("https://www.google.com"),
		chromedp.Sleep(2*time.Second),
		chromedp.Title(&title2),
	)

	duration2 := time.Since(start2)

	fmt.Printf("  Duration: %v\n", duration2)
	fmt.Printf("  Error: %v\n", err2)
	fmt.Printf("  Title: %s\n", title2)

	if err2 != nil && duration2 < time.Second {
		fmt.Println("  ❌ FAILED TOO FAST - Context issue\n")
	} else if err2 != nil {
		fmt.Println("  ❌ FAILED with error\n")
	} else {
		fmt.Println("  ✅ SUCCESS\n")
	}

	fmt.Println("========================================")
	fmt.Println("Test complete")
	fmt.Println("========================================")
}
