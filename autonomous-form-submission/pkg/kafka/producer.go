package kafka

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/IBM/sarama"
	"go.uber.org/zap"
)

// Producer wraps Kafka producer with retry logic
type Producer struct {
	producer sarama.SyncProducer
	logger   *zap.Logger
}

// ProducerConfig contains Kafka producer configuration
type ProducerConfig struct {
	Brokers []string
	Logger  *zap.Logger
}

// NewProducer creates a new Kafka producer
func NewProducer(config ProducerConfig) (*Producer, error) {
	saramaConfig := sarama.NewConfig()
	saramaConfig.Producer.RequiredAcks = sarama.WaitForAll
	saramaConfig.Producer.Retry.Max = 5
	saramaConfig.Producer.Return.Successes = true
	saramaConfig.Producer.Compression = sarama.CompressionSnappy
	saramaConfig.Version = sarama.V2_8_0_0

	producer, err := sarama.NewSyncProducer(config.Brokers, saramaConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create Kafka producer: %w", err)
	}

	config.Logger.Info("Kafka producer created", zap.Strings("brokers", config.Brokers))

	return &Producer{
		producer: producer,
		logger:   config.Logger,
	}, nil
}

// PublishMessage publishes a message to a Kafka topic
func (p *Producer) PublishMessage(topic string, key string, value interface{}) error {
	// Serialize value to JSON
	valueBytes, err := json.Marshal(value)
	if err != nil {
		return fmt.Errorf("failed to marshal message: %w", err)
	}

	msg := &sarama.ProducerMessage{
		Topic:     topic,
		Key:       sarama.StringEncoder(key),
		Value:     sarama.ByteEncoder(valueBytes),
		Timestamp: time.Now(),
	}

	partition, offset, err := p.producer.SendMessage(msg)
	if err != nil {
		p.logger.Error("failed to publish message",
			zap.String("topic", topic),
			zap.String("key", key),
			zap.Error(err),
		)
		return fmt.Errorf("failed to publish message: %w", err)
	}

	p.logger.Debug("message published",
		zap.String("topic", topic),
		zap.String("key", key),
		zap.Int32("partition", partition),
		zap.Int64("offset", offset),
	)

	return nil
}

// PublishBatch publishes multiple messages to a Kafka topic
func (p *Producer) PublishBatch(topic string, messages []Message) error {
	for _, msg := range messages {
		if err := p.PublishMessage(topic, msg.Key, msg.Value); err != nil {
			return err
		}
	}

	p.logger.Info("batch published",
		zap.String("topic", topic),
		zap.Int("count", len(messages)),
	)

	return nil
}

// Close closes the producer
func (p *Producer) Close() error {
	if err := p.producer.Close(); err != nil {
		return fmt.Errorf("failed to close producer: %w", err)
	}
	p.logger.Info("Kafka producer closed")
	return nil
}

// Message represents a message to be published
type Message struct {
	Key   string
	Value interface{}
}
