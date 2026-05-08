package browser

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/chromedp/chromedp"
	"go.uber.org/zap"
)

type contextWrapper struct {
	ctx        context.Context
	cancel     context.CancelFunc
	lastUsed   time.Time
	inUse      bool
}

// ContextPool manages a pool of browser contexts for concurrent operations
type ContextPool struct {
	size            int
	contexts        chan *contextWrapper
	wrappers        []*contextWrapper
	allocCtx        context.Context
	allocCancel     context.CancelFunc
	mu              sync.Mutex
	logger          *zap.Logger
	headless        bool
	idleTimeout     time.Duration
	cleanupTicker   *time.Ticker
	cleanupDone     chan bool
}

// NewContextPool creates a new browser context pool with idle timeout support
func NewContextPool(size int, headless bool, logger *zap.Logger) (*ContextPool, error) {
	return NewContextPoolWithTimeout(size, headless, 0, logger)
}

// NewContextPoolWithTimeout creates a new browser context pool with configurable idle timeout
func NewContextPoolWithTimeout(size int, headless bool, idleTimeout time.Duration, logger *zap.Logger) (*ContextPool, error) {
	if size <= 0 {
		return nil, fmt.Errorf("pool size must be positive")
	}

	// Create base allocator with stealth options
	opts := append(chromedp.DefaultExecAllocatorOptions[:],
		GetChromeOptions()...,
	)
	
	if headless {
		opts = append(opts, chromedp.Headless)
	}

	allocCtx, allocCancel := chromedp.NewExecAllocator(context.Background(), opts...)

	pool := &ContextPool{
		size:        size,
		contexts:    make(chan *contextWrapper, size),
		wrappers:    make([]*contextWrapper, 0, size),
		allocCtx:    allocCtx,
		allocCancel: allocCancel,
		logger:      logger,
		headless:    headless,
		idleTimeout: idleTimeout,
		cleanupDone: make(chan bool),
	}

	// Create initial browser contexts
	for i := 0; i < size; i++ {
		wrapper, err := pool.createContext()
		if err != nil {
			pool.Close()
			return nil, fmt.Errorf("failed to create browser context %d: %w", i, err)
		}
		pool.wrappers = append(pool.wrappers, wrapper)
		pool.contexts <- wrapper
	}

	// Start cleanup goroutine if idle timeout is configured
	if idleTimeout > 0 {
		pool.cleanupTicker = time.NewTicker(idleTimeout / 2)
		go pool.cleanupIdleContexts()
		logger.Info("browser context pool initialized with idle timeout",
			zap.Int("size", size),
			zap.Duration("idle_timeout", idleTimeout),
		)
	} else {
		logger.Info("browser context pool initialized", zap.Int("size", size))
	}

	return pool, nil
}

// createContext creates a new browser context wrapper
func (p *ContextPool) createContext() (*contextWrapper, error) {
	ctx, cancel := chromedp.NewContext(p.allocCtx)

	// Initialize the browser
	if err := chromedp.Run(ctx); err != nil {
		cancel()
		return nil, fmt.Errorf("failed to initialize browser context: %w", err)
	}

	// Apply stealth mode
	stealthConfig := NewStealthConfig()
	if err := ApplyStealthMode(ctx, stealthConfig); err != nil {
		p.logger.Warn("failed to apply stealth mode", zap.Error(err))
	}

	wrapper := &contextWrapper{
		ctx:      ctx,
		cancel:   cancel,
		lastUsed: time.Now(),
		inUse:    false,
	}

	return wrapper, nil
}

// Acquire gets a browser context from the pool
func (p *ContextPool) Acquire() context.Context {
	wrapper := <-p.contexts
	p.mu.Lock()
	defer p.mu.Unlock()

	// If context was closed due to idle timeout, recreate it
	if wrapper.ctx == nil {
		newWrapper, err := p.createContext()
		if err != nil {
			p.logger.Error("failed to recreate browser context", zap.Error(err))
			// Put back the wrapper and return the old (nil) context
			// This will cause an error downstream, but we've logged it
			wrapper.inUse = true
			wrapper.lastUsed = time.Now()
			return wrapper.ctx
		}
		// Replace the old wrapper with the new one
		for i, w := range p.wrappers {
			if w == wrapper {
				p.wrappers[i] = newWrapper
				break
			}
		}
		wrapper = newWrapper
		p.logger.Info("recreated browser context after idle timeout")
	}

	wrapper.inUse = true
	wrapper.lastUsed = time.Now()
	return wrapper.ctx
}

// Release returns a browser context to the pool
func (p *ContextPool) Release(ctx context.Context) {
	p.mu.Lock()
	defer p.mu.Unlock()

	for _, wrapper := range p.wrappers {
		if wrapper.ctx == ctx {
			wrapper.inUse = false
			wrapper.lastUsed = time.Now()
			p.contexts <- wrapper
			return
		}
	}
	p.logger.Warn("attempted to release unknown context")
}

// cleanupIdleContexts periodically closes idle contexts to free resources
func (p *ContextPool) cleanupIdleContexts() {
	for {
		select {
		case <-p.cleanupTicker.C:
			p.mu.Lock()
			now := time.Now()
			closedCount := 0

			for _, wrapper := range p.wrappers {
				if !wrapper.inUse && wrapper.ctx != nil {
					idleTime := now.Sub(wrapper.lastUsed)
					if idleTime > p.idleTimeout {
						p.logger.Info("closing idle browser context",
							zap.Duration("idle_time", idleTime),
						)
						wrapper.cancel()
						wrapper.ctx = nil
						wrapper.cancel = nil
						closedCount++
					}
				}
			}

			if closedCount > 0 {
				p.logger.Info("closed idle browser contexts",
					zap.Int("count", closedCount),
				)
			}
			p.mu.Unlock()

		case <-p.cleanupDone:
			return
		}
	}
}

// Close closes all browser contexts in the pool
func (p *ContextPool) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	// Stop cleanup goroutine
	if p.cleanupTicker != nil {
		p.cleanupTicker.Stop()
		close(p.cleanupDone)
	}

	// Close the contexts channel
	close(p.contexts)

	// Cancel all contexts
	for _, wrapper := range p.wrappers {
		if wrapper.cancel != nil {
			wrapper.cancel()
		}
	}

	// Cancel the allocator
	if p.allocCancel != nil {
		p.allocCancel()
	}

	p.logger.Info("browser context pool closed")
	return nil
}

// Size returns the pool size
func (p *ContextPool) Size() int {
	return p.size
}
