'use strict';

// ── InMemoryQueue ─────────────────────────────────────────────────────────────
// Simple FIFO backed by an array + index pointer.
// All methods are async so the interface is identical to RedisQueue.

class InMemoryQueue {
  constructor(items = []) {
    this.items = Array.isArray(items) ? items.slice() : [];
    this.index = 0;
  }

  async pop() {
    return this.index < this.items.length ? this.items[this.index++] : null;
  }

  async push(item) {
    this.items.push(item);
  }

  async pushMany(items) {
    for (const item of items) this.items.push(item);
  }

  async size() {
    return this.items.length - this.index;
  }

  async close() {}
}

// ── RedisQueue ────────────────────────────────────────────────────────────────
// FIFO backed by a Redis LIST.
//   RPUSH → enqueue at tail
//   LPOP  → dequeue from head  (atomic, safe for multiple concurrent consumers)
//
// Requires: npm install ioredis
// The ioredis client is injected so the caller controls the connection options.

class RedisQueue {
  constructor(client, key = 'humres:urls') {
    this.client = client;
    this.key = key;
  }

  async pop() {
    const value = await this.client.lpop(this.key);
    return value !== null && value !== undefined ? value : null;
  }

  async push(item) {
    await this.client.rpush(this.key, item);
  }

  // Push a large batch in one round-trip
  async pushMany(items) {
    if (!items.length) return;
    await this.client.rpush(this.key, ...items);
  }

  async size() {
    return this.client.llen(this.key);
  }

  async close() {
    await this.client.quit();
  }
}

// ── Factory ───────────────────────────────────────────────────────────────────
// Creates the right queue implementation from a type string.
//
// opts for 'memory': { items: string[] }
// opts for 'redis':  { redisUrl: string, key?: string }

async function createQueue(type, opts = {}) {
  if (type === 'redis') {
    // Lazy-require so ioredis is only needed when Redis mode is actually used
    let Redis;
    try {
      Redis = require('ioredis');
    } catch {
      throw new Error(
        'ioredis is not installed. Run: npm install ioredis'
      );
    }
    const client = new Redis(opts.redisUrl || 'redis://127.0.0.1:6379', {
      lazyConnect: false,
      maxRetriesPerRequest: 3,
    });
    return new RedisQueue(client, opts.key || 'humres:urls');
  }

  return new InMemoryQueue(opts.items || []);
}

module.exports = { InMemoryQueue, RedisQueue, createQueue };
