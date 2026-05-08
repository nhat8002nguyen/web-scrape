package main

import (
	"context"
	"fmt"
	"time"

	"github.com/chromedp/chromedp"
)

func main() {
	fmt.Println("========================================")
	fmt.Println("Minimal chromedp Test")
	fmt.Println("========================================")
	fmt.Println()

	// Test 1: Basic chromedp with context.Background()
	fmt.Println("Test 1: Basic navigation with context.Background()")
	ctx1, cancel1 := chromedp.NewContext(context.Background())
	defer cancel1()

	start1 := time.Now()
	err1 := chromedp.Run(ctx1,
		chromedp.Navigate("https://example.com"),
		chromedp.Sleep(2*time.Second),
	)
	duration1 := time.Since(start1)

	fmt.Printf("  Duration: %v\n", duration1)
	fmt.Printf("  Error: %v\n", err1)
	if err1 == nil {
		fmt.Println("  ✅ SUCCESS")
	} else if duration1 < time.Second {
		fmt.Println("  ❌ FAILED INSTANTLY - Context already canceled")
	} else {
		fmt.Println("  ❌ FAILED after timeout")
	}
	fmt.Println()

	// Test 2: With timeout context
	fmt.Println("Test 2: With 45-second timeout")
	ctx2, cancel2 := chromedp.NewContext(context.Background())
	defer cancel2()

	timeoutCtx, timeoutCancel := context.WithTimeout(ctx2, 45*time.Second)
	defer timeoutCancel()

	start2 := time.Now()
	err2 := chromedp.Run(timeoutCtx,
		chromedp.Navigate("https://vietnam.acclime.com/"),
		chromedp.Sleep(2*time.Second),
	)
	duration2 := time.Since(start2)

	fmt.Printf("  Duration: %v\n", duration2)
	fmt.Printf("  Error: %v\n", err2)
	if err2 == nil {
		fmt.Println("  ✅ SUCCESS")
	} else if duration2 < time.Second {
		fmt.Println("  ❌ FAILED INSTANTLY - Context already canceled")
	} else {
		fmt.Println("  ❌ FAILED after timeout")
	}
	fmt.Println()

	fmt.Println("========================================")
	fmt.Println("CONCLUSION:")
	fmt.Println("========================================")
	if err1 == nil {
		fmt.Println("✅ chromedp works fine - issue is in worker code")
	} else {
		fmt.Println("❌ chromedp itself is broken - Chrome/system issue")
	}
	fmt.Println()
}
