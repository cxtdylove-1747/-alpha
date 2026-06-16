export const asArray = (value) => {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.results)) return value.results;
  return [];
};

export const paginate = (items, currentPage = 1, pageSize = 8) => {
  const safeItems = Array.isArray(items) ? items : [];
  const start = (currentPage - 1) * pageSize;
  return safeItems.slice(start, start + pageSize);
};

export const normalizePagedResult = (value) => {
  const items = asArray(value);
  const totalRaw = value?.total ?? value?.count ?? value?.pagination?.total;
  const total = Number.isFinite(Number(totalRaw)) ? Number(totalRaw) : items.length;
  const serverPaged = value && typeof value === 'object' && !Array.isArray(value)
    && (Object.prototype.hasOwnProperty.call(value, 'total') || Object.prototype.hasOwnProperty.call(value, 'count'));
  return { items, total, serverPaged };
};

export const compactQuery = (params = {}) => Object.fromEntries(
  Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined)
);


