import 'package:flutter_test/flutter_test.dart';

import 'package:jobify_app/presentation/routing/router.dart';

void main() {
  group('safeNextLocation', () {
    test('returns null for null and empty', () {
      expect(safeNextLocation(null), isNull);
      expect(safeNextLocation(''), isNull);
    });

    test('decodes URI-encoded path', () {
      expect(
        safeNextLocation('%2Ffeed%2Fjobs%2Fabc-123'),
        '/feed/jobs/abc-123',
      );
    });

    test('rejects open-redirect targets', () {
      // Absolute URLs to other origins must NOT be honoured.
      expect(safeNextLocation('https://evil.example.com/x'), isNull);
      expect(safeNextLocation('http://evil.example.com/'), isNull);
      // Protocol-relative URLs — they would inherit the current scheme.
      expect(safeNextLocation('//evil.example.com/x'), isNull);
      // Decoded form must still pass the prefix checks.
      expect(safeNextLocation('%2F%2Fevil.example.com'), isNull);
    });

    test('rejects non-path inputs', () {
      expect(safeNextLocation('feed'), isNull); // missing leading /
      expect(safeNextLocation('about:blank'), isNull);
    });

    test('refuses to redirect back to /signin (avoids loop)', () {
      expect(safeNextLocation('/signin'), isNull);
    });

    test('accepts known protected routes verbatim', () {
      expect(safeNextLocation('/feed'), '/feed');
      expect(safeNextLocation('/saved'), '/saved');
      expect(safeNextLocation('/applications'), '/applications');
      expect(safeNextLocation('/profile'), '/profile');
      expect(safeNextLocation('/profile/edit'), '/profile/edit');
      expect(
        safeNextLocation('/applications/jobs/abc-123'),
        '/applications/jobs/abc-123',
      );
    });
  });
}
