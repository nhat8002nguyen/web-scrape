package browser

import (
	"context"
	"fmt"
	"math/rand"
	"time"

	"github.com/chromedp/chromedp"
)

// StealthConfig contains anti-detection configurations
type StealthConfig struct {
	UserAgent  string
	ViewportWidth int
	ViewportHeight int
	Language   string
	Platform   string
}

// NewStealthConfig creates a randomized stealth configuration
func NewStealthConfig() *StealthConfig {
	viewports := []struct{ width, height int }{
		{1920, 1080},
		{1366, 768},
		{1440, 900},
		{1536, 864},
		{1680, 1050},
	}
	
	viewport := viewports[rand.Intn(len(viewports))]
	
	return &StealthConfig{
		UserAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		ViewportWidth: viewport.width,
		ViewportHeight: viewport.height,
		Language: "en-US,en;q=0.9",
		Platform: "MacIntel",
	}
}

// GetStealthScript returns JavaScript to inject for stealth mode
func GetStealthScript() string {
	return `
(function() {
	// Override navigator.webdriver
	Object.defineProperty(navigator, 'webdriver', {
		get: () => undefined
	});

	// Override navigator.plugins
	Object.defineProperty(navigator, 'plugins', {
		get: () => [
			{
				0: {type: "application/pdf", suffixes: "pdf", description: "Portable Document Format"},
				description: "Portable Document Format",
				filename: "internal-pdf-viewer",
				length: 1,
				name: "Chrome PDF Plugin"
			},
			{
				0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
				description: "Portable Document Format",
				filename: "internal-pdf-viewer",
				length: 1,
				name: "Chrome PDF Viewer"
			},
			{
				0: {type: "application/x-nacl", suffixes: "", description: "Native Client Executable"},
				description: "Native Client Executable",
				filename: "internal-nacl-plugin",
				length: 2,
				name: "Native Client"
			}
		]
	});

	// Override navigator.languages
	Object.defineProperty(navigator, 'languages', {
		get: () => ['en-US', 'en']
	});

	// Override chrome runtime
	window.chrome = {
		runtime: {}
	};

	// Override permissions
	const originalQuery = window.navigator.permissions.query;
	window.navigator.permissions.query = (parameters) => (
		parameters.name === 'notifications' ?
			Promise.resolve({state: Notification.permission}) :
			originalQuery(parameters)
	);

	// Override WebGL vendor
	const getParameter = WebGLRenderingContext.prototype.getParameter;
	WebGLRenderingContext.prototype.getParameter = function(parameter) {
		if (parameter === 37445) {
			return 'Intel Inc.';
		}
		if (parameter === 37446) {
			return 'Intel Iris OpenGL Engine';
		}
		return getParameter.apply(this, arguments);
	};

	// Override screen resolution
	Object.defineProperty(screen, 'width', {
		get: () => window.innerWidth
	});
	Object.defineProperty(screen, 'height', {
		get: () => window.innerHeight
	});
	Object.defineProperty(screen, 'availWidth', {
		get: () => window.innerWidth
	});
	Object.defineProperty(screen, 'availHeight', {
		get: () => window.innerHeight
	});

	// Override devicePixelRatio
	Object.defineProperty(window, 'devicePixelRatio', {
		get: () => 2
	});

	// Hide automation-specific properties
	delete navigator.__proto__.webdriver;
})();
`
}

// ApplyStealthMode applies anti-detection measures to the browser context
func ApplyStealthMode(ctx context.Context, config *StealthConfig) error {
	// Inject stealth script before any page loads
	if err := chromedp.Run(ctx,
		chromedp.ActionFunc(func(ctx context.Context) error {
			return chromedp.Evaluate(GetStealthScript(), nil).Do(ctx)
		}),
	); err != nil {
		return fmt.Errorf("failed to inject stealth script: %w", err)
	}
	
	return nil
}

// SimulateHumanBehavior adds random delays and movements to appear more human
func SimulateHumanBehavior(ctx context.Context) error {
	// Random delay between 500ms and 2000ms
	delay := time.Duration(500+rand.Intn(1500)) * time.Millisecond
	
	select {
	case <-time.After(delay):
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

// TypeLikeHuman types text with random delays between keystrokes
func TypeLikeHuman(ctx context.Context, selector, text string) error {
	for _, char := range text {
		if err := chromedp.Run(ctx,
			chromedp.Focus(selector),
			chromedp.SendKeys(selector, string(char)),
		); err != nil {
			return err
		}
		
		// Random delay between 50ms and 150ms per character
		delay := time.Duration(50+rand.Intn(100)) * time.Millisecond
		select {
		case <-time.After(delay):
		case <-ctx.Done():
			return ctx.Err()
		}
	}
	
	return nil
}

// ScrollToElement scrolls an element into view smoothly
func ScrollToElement(ctx context.Context, selector string) error {
	script := fmt.Sprintf(`
		const element = document.querySelector('%s');
		if (element) {
			element.scrollIntoView({behavior: 'smooth', block: 'center'});
		}
	`, selector)
	
	return chromedp.Run(ctx,
		chromedp.Evaluate(script, nil),
		chromedp.Sleep(500*time.Millisecond),
	)
}

// RandomMouseMovement simulates random mouse movements
func RandomMouseMovement(ctx context.Context) error {
	x := rand.Intn(800) + 100
	y := rand.Intn(600) + 100
	
	script := fmt.Sprintf(`
		const event = new MouseEvent('mousemove', {
			clientX: %d,
			clientY: %d,
			bubbles: true
		});
		document.dispatchEvent(event);
	`, x, y)
	
	return chromedp.Run(ctx, chromedp.Evaluate(script, nil))
}

// GetChromeOptions returns recommended Chrome launch options for stealth
func GetChromeOptions() []chromedp.ExecAllocatorOption {
	return []chromedp.ExecAllocatorOption{
		chromedp.NoFirstRun,
		chromedp.NoDefaultBrowserCheck,
		chromedp.DisableGPU,
		chromedp.Flag("disable-blink-features", "AutomationControlled"),
		chromedp.Flag("excludeSwitches", "enable-automation"),
		chromedp.Flag("disable-extensions", false),
		chromedp.Flag("disable-dev-shm-usage", true),
		chromedp.Flag("no-sandbox", true),
		chromedp.Flag("disable-setuid-sandbox", true),
		chromedp.Flag("disable-web-security", false),
		chromedp.Flag("disable-features", "IsolateOrigins,site-per-process"),
		chromedp.UserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
	}
}
