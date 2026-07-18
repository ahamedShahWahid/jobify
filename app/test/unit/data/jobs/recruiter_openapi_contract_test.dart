import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('backend recruiter schemas pin the expected wire fields', () {
    final snapshot = jsonDecode(
      File('../tests/unit/openapi_snapshot.json').readAsStringSync(),
    ) as Map<String, dynamic>;
    final components = snapshot['components'] as Map<String, dynamic>;
    final schemas = components['schemas'] as Map<String, dynamic>;

    const expected = <String, Set<String>>{
      'RecruiterJobRow': {
        'applicant_count',
        'ctc_max',
        'ctc_min',
        'description',
        'employer_verified',
        'id',
        'locations',
        'max_exp_years',
        'min_exp_years',
        'posted_at',
        'status',
        'surfaced_match_count',
        'title',
      },
      'ApplicantOfJobRow': {
        'applicant_id',
        'application_id',
        'applied_at',
        'display_name',
        'email',
        'match_explanation',
        'match_score',
        'status',
      },
      'ApplicantsOfJobPage': {'items', 'next_cursor'},
      'MemberRead': {'added_at', 'display_name', 'email', 'role', 'user_id'},
      'InviteRead': {
        'created_at',
        'email',
        'employer_id',
        'expires_at',
        'id',
        'invited_by_user_id',
        'role',
        'status',
      },
    };

    for (final entry in expected.entries) {
      final schema = schemas[entry.key] as Map<String, dynamic>;
      final properties = schema['properties'] as Map<String, dynamic>;
      expect(properties.keys.toSet(), entry.value, reason: entry.key);
    }
  });
}
