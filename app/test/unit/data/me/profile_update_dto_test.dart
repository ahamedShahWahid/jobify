import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/me/profile_update_dto.dart';

void main() {
  test('toJson uses snake_case keys and includes explicit nulls', () {
    const dto = ProfileUpdateDto(
      fullName: 'Alice Khan',
      noticePeriodDays: 30,
      currentCtc: 1200000,
      yearsExperience: 4.5,
    );
    final json = dto.toJson();

    expect(json['full_name'], 'Alice Khan');
    expect(json['notice_period_days'], 30);
    expect(json['current_ctc'], 1200000);
    expect(json['years_experience'], 4.5);
  });

  test('toJson includes unset fields as explicit null (clears persist)', () {
    const dto = ProfileUpdateDto(fullName: 'Alice Khan');
    final json = dto.toJson();

    expect(json['full_name'], 'Alice Khan');
    expect(json.containsKey('notice_period_days'), isTrue);
    expect(json['notice_period_days'], isNull);
    expect(json.containsKey('current_ctc'), isTrue);
    expect(json['current_ctc'], isNull);
    expect(json.containsKey('years_experience'), isTrue);
    expect(json['years_experience'], isNull);
  });
}
