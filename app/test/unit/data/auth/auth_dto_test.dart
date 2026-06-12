import 'package:flutter_test/flutter_test.dart';
import 'package:jobify_app/data/auth/auth_dto.dart';

// These fixtures mirror the REAL backend wire shape (api/src/jobify/routes/auth.py:
// SignInResponse / RefreshResponse), NOT the Dart field names. They guard the
// JSON-key contract so a future rename on either side fails loudly here instead
// of surfacing as a generic "Sign-in failed" snackbar on a 200 OK.
void main() {
  group('SignInResponseDto.fromJson against real backend shape', () {
    test('maps access_token/refresh_token wire keys', () {
      final dto = SignInResponseDto.fromJson(const {
        'access_token': 'ACCESS',
        'refresh_token': 'REFRESH',
        'token_type': 'Bearer',
        'expires_in': 600,
        'user': {
          'id': 'uid-1',
          'email': 'user@example.com',
          'role': 'applicant',
          'applicant_id': 'app-1',
          'is_new_user': true,
        },
      });

      expect(dto.access, 'ACCESS');
      expect(dto.refresh, 'REFRESH');
      expect(dto.user.id, 'uid-1');
      expect(dto.user.email, 'user@example.com');
      expect(dto.user.role, 'applicant');
      // Backend omits display_name on this endpoint — must parse to null,
      // not throw.
      expect(dto.user.displayName, isNull);
    });
  });

  group('RefreshResponseDto.fromJson against real backend shape', () {
    test('maps access_token/refresh_token wire keys', () {
      final dto = RefreshResponseDto.fromJson(const {
        'access_token': 'NEW_ACCESS',
        'refresh_token': 'NEW_REFRESH',
        'token_type': 'Bearer',
        'expires_in': 600,
      });

      expect(dto.access, 'NEW_ACCESS');
      expect(dto.refresh, 'NEW_REFRESH');
    });
  });
}
