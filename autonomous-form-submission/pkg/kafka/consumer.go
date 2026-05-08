package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/IBM/sarama"
	"go.uber.org/zap"
)

// MessageHandler is a function that processes consumed messages
type MessageHandler func(ctx context.Context, message []byte) error

// Consumer wraps Kafka consumer with retry logic
type Consumer struct {
	group         sarama.ConsumerGroup
	topics        []string
	handler       MessageHandler
	logger        *zap.Logger
	retryAttempts int
	retryDelay    time.Duration
	wg            sync.WaitGroup
	cancel        context.CancelFunc
}

// ConsumerConfig contains Kafka consumer configuration
type ConsumerConfig struct {
	Brokers       []string
	GroupID       string
	Topics        []string
	Handler       MessageHandler
	Logger        *zap.Logger
	RetryAttempts int
	RetryDelay    time.Duration
}

// NewConsumer creates a new Kafka consumer
func NewConsumer(config ConsumerConfig) (*Consumer, error) {
	saramaConfig := sarama.NewConfig()
	saramaConfig.Version = sarama.V2_8_0_0
	saramaConfig.Consumer.Group.Rebalance.Strategy = sarama.NewBalanceStrategyRoundRobin()
	saramaConfig.Consumer.Offsets.Initial = sarama.OffsetOldest
	saramaConfig.Consumer.Offsets.AutoCommit.Enable = true
	saramaConfig.Consumer.Offsets.AutoCommit.Interval = 1 * time.Second
	saramaConfig.Consumer.Return.Errors = true

	group, err := sarama.NewConsumerGroup(config.Brokers, config.GroupID, saramaConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create consumer group: %w", err)
	}

	if config.RetryAttempts == 0 {
		config.RetryAttempts = 3
	}
	if config.RetryDelay == 0 {
		config.RetryDelay = 2 * time.Second
	}

	config.Logger.Info("Kafka consumer created",
		zap.Strings("brokers", config.Brokers),
		zap.String("group_id", config.GroupID),
		zap.Strings("topics", config.Topics),
	)

	return &Consumer{
		group:         group,
		topics:        config.Topics,
		handler:       config.Handler,
		logger:        config.Logger,
		retryAttempts: config.RetryAttempts,
		retryDelay:    config.RetryDelay,
	}, nil
}

// Start starts consuming messages
func (c *Consumer) Start(ctx context.Context) error {
	ctx, cancel := context.WithCancel(ctx)
	c.cancel = cancel

	handler := &consumerGroupHandler{
		consumer: c,
		logger:   c.logger,
	}

	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		for {
			if err := c.group.Consume(ctx, c.topics, handler); err != nil {
				c.logger.Error("error from consumer", zap.Error(err))
			}

			if ctx.Err() != nil {
				return
			}
		}
	}()

	// Handle errors
	c.wg.Add(1)
	go func() {
		defer c.wg.Done()
		for err := range c.group.Errors() {
			c.logger.Error("consumer group error", zap.Error(err))
		}
	}()

	c.logger.Info("Kafka consumer started", zap.Strings("topics", c.topics))
	return nil
}

// Stop stops the consumer
func (c *Consumer) Stop() error {
	if c.cancel != nil {
		c.cancel()
	}

	c.wg.Wait()

	if err := c.group.Close(); err != nil {
		return fmt.Errorf("failed to close consumer group: %w", err)
	}

	c.logger.Info("Kafka consumer stopped")
	return nil
}

// consumerGroupHandler implements sarama.ConsumerGroupHandler
type consumerGroupHandler struct {
	consumer *Consumer
	logger   *zap.Logger
}

func (h *consumerGroupHandler) Setup(sarama.ConsumerGroupSession) error {
	return nil
}

func (h *consumerGroupHandler) Cleanup(sarama.ConsumerGroupSession) error {
	return nil
}

func (h *consumerGroupHandler) ConsumeClaim(session sarama.ConsumerGroupSession, claim sarama.ConsumerGroupClaim) error {
	for message := range claim.Messages() {
		ctx := session.Context()

		// Process message with retries
		err := h.processWithRetry(ctx, message.Value)

		if err != nil {
			h.logger.Error("failed to process message after retries",
				zap.String("topic", message.Topic),
				zap.Int32("partition", message.Partition),
				zap.Int64("offset", message.Offset),
				zap.Error(err),
			)
			// Still mark as consumed to avoid blocking
			session.MarkMessage(message, "")
		} else {
			// Mark message as processed
			session.MarkMessage(message, "")

			h.logger.Debug("message processed",
				zap.String("topic", message.Topic),
				zap.Int32("partition", message.Partition),
				zap.Int64("offset", message.Offset),
			)
		}
	}

	return nil
}

func (h *consumerGroupHandler) processWithRetry(ctx context.Context, message []byte) error {
	var lastErr error

	for attempt := 0; attempt <= h.consumer.retryAttempts; attempt++ {
		if attempt > 0 {
			h.logger.Warn("retrying message processing",
				zap.Int("attempt", attempt),
				zap.Int("max_attempts", h.consumer.retryAttempts),
			)

			select {
			case <-time.After(h.consumer.retryDelay):
			case <-ctx.Done():
				return ctx.Err()
			}
		}

		err := h.consumer.handler(ctx, message)
		if err == nil {
			return nil
		}

		lastErr = err
	}

	return fmt.Errorf("failed after %d attempts: %w", h.consumer.retryAttempts, lastErr)
}

// UnmarshalMessage unmarshals a message into a struct
func UnmarshalMessage(data []byte, v interface{}) error {
	if err := json.Unmarshal(data, v); err != nil {
		return fmt.Errorf("failed to unmarshal message: %w", err)
	}
	return nil
}
