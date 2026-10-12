/** Fixed-capacity buffer; the newest item overwrites the oldest. Keeps memory bounded. */
export class RingBuffer<T> {
  readonly capacity: number;
  private items: (T | undefined)[];
  private head = 0;
  private count = 0;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.items = new Array<T | undefined>(capacity);
  }

  get size(): number {
    return this.count;
  }

  push(item: T): void {
    this.items[(this.head + this.count) % this.capacity] = item;
    if (this.count < this.capacity) this.count++;
    else this.head = (this.head + 1) % this.capacity;
  }

  /** i = 0 is the oldest item. */
  at(i: number): T | undefined {
    if (i < 0 || i >= this.count) return undefined;
    return this.items[(this.head + i) % this.capacity];
  }

  last(): T | undefined {
    return this.at(this.count - 1);
  }

  /** Oldest first. */
  toArray(): T[] {
    const out = new Array<T>(this.count);
    for (let i = 0; i < this.count; i++) out[i] = this.items[(this.head + i) % this.capacity] as T;
    return out;
  }

  clear(): void {
    this.items = new Array<T | undefined>(this.capacity);
    this.head = 0;
    this.count = 0;
  }
}
