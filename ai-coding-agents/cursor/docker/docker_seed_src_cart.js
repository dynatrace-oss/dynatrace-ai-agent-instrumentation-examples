export function subtotal(items) {
  return items.reduce((sum, item) => sum + item.price * (item.quantity || 1), 0);
}

export function applyDiscount(total, percentage) {
  return Math.round(total * (1 - percentage / 100));
}
