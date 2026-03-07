export function formatDateShort(date: Date): string {
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function formatDateComment(date: Date): string {
  const datePart = date.toISOString().slice(0, 10); // YYYY-MM-DD
  const timePart = date.toISOString().slice(11, 16); // HH:MM
  return `${datePart} ${timePart} UTC`;
}

export function formatDate(date: Date): string {
  const weekday = date.toLocaleDateString("en-GB", { weekday: "long", timeZone: "UTC" });
  const day = date.toLocaleDateString("en-GB", { day: "2-digit", timeZone: "UTC" });
  const month = date.toLocaleDateString("en-GB", { month: "long", timeZone: "UTC" });
  const year = date.toLocaleDateString("en-GB", { year: "numeric", timeZone: "UTC" });
  const time = date.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "UTC",
    hour12: false,
  });
  return `${weekday}, ${day} ${month} ${year} ${time} UTC`;
}
