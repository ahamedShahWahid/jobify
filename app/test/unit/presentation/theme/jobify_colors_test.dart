import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/presentation/theme/jobify_colors.dart';

void main() {
  test('brand blue is the one meaning color', () {
    expect(JobifyColors.brandBlueLight, const Color(0xFF0048A8));
    expect(JobifyColors.brandBlueDark, const Color(0xFF5B9BFF));
  });

  test('caveat amber is defined for both themes', () {
    expect(JobifyColors.caveatLight, const Color(0xFFC77A1E));
    expect(JobifyColors.caveatDark, const Color(0xFFE0A24A));
  });

  test('surface is cool sky / calm night (not warm, not black)', () {
    expect(JobifyColors.paperLight, const Color(0xFFF4F6F9));
    expect(JobifyColors.paperDark, const Color(0xFF0B1620));
  });
}
