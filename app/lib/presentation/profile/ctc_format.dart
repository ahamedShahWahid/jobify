import 'package:intl/intl.dart';

// Module-static: NumberFormat parses its pattern on construction.
final _inr = NumberFormat.currency(
  locale: 'en_IN',
  symbol: '₹',
  decimalDigits: 0,
);

/// Format a wire CTC string (Pydantic Decimal → JSON string) as Indian-grouped
/// rupees. Returns '—' for null/unparseable.
String formatCtc(String? raw) {
  if (raw == null) return '—';
  final v = double.tryParse(raw);
  if (v == null) return '—';
  return _inr.format(v);
}

/// Format a recruiter-side CTC float (e.g. 1800000.0) as Indian-grouped
/// rupees. Returns '—' for null.
String formatCtcNum(double? value) {
  if (value == null) return '—';
  return _inr.format(value);
}

/// Format a wire years-of-experience string (e.g. "5.0", "4.5") for display:
/// drops a trailing ".0" so whole numbers read cleanly. Returns null for
/// null/unparseable so the caller can hide the row.
String? formatYears(String? raw) {
  if (raw == null) return null;
  final v = double.tryParse(raw);
  if (v == null) return null;
  final n = v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toString();
  return '$n yrs';
}
