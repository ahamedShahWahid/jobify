import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/profile/ctc_format.dart';

void main() {
  test('formats Indian-grouped rupees', () {
    expect(formatCtc('1200000.00'), '₹12,00,000');
  });
  test('null and unparseable → dash', () {
    expect(formatCtc(null), '—');
    expect(formatCtc('abc'), '—');
  });

  test('formatYears drops trailing .0 but keeps real decimals', () {
    expect(formatYears('5.0'), '5 yrs');
    expect(formatYears('4.5'), '4.5 yrs');
  });
  test('formatYears null/unparseable → null', () {
    expect(formatYears(null), isNull);
    expect(formatYears('abc'), isNull);
  });
}
