import 'package:flutter_test/flutter_test.dart';
import 'package:kpa_app/data/auth/token_storage.dart';

/// In-memory implementation. We don't test SecureTokenStorage directly
/// because flutter_secure_storage uses platform channels not available
/// in unit tests. The integration test (Task 35) exercises the real
/// plugin in a tester context.
class InMemoryTokenStorage implements TokenStorage {
  String? _t;
  @override
  Future<String?> readRefreshToken() async => _t;
  @override
  Future<void> writeRefreshToken(String token) async => _t = token;
  @override
  Future<void> clear() async => _t = null;
}

void main() {
  group('TokenStorage contract', () {
    late TokenStorage storage;
    setUp(() => storage = InMemoryTokenStorage());

    test('write then read returns the token', () async {
      await storage.writeRefreshToken('rt-1');
      expect(await storage.readRefreshToken(), 'rt-1');
    });

    test('clear removes the token', () async {
      await storage.writeRefreshToken('rt-1');
      await storage.clear();
      expect(await storage.readRefreshToken(), isNull);
    });

    test('read on empty storage returns null', () async {
      expect(await storage.readRefreshToken(), isNull);
    });

    test('write overwrites previous value', () async {
      await storage.writeRefreshToken('rt-1');
      await storage.writeRefreshToken('rt-2');
      expect(await storage.readRefreshToken(), 'rt-2');
    });
  });
}
