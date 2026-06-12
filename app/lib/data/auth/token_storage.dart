import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'token_storage.g.dart';

abstract interface class TokenStorage {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String token);
  Future<void> clear();
}

class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage([FlutterSecureStorage? storage])
      : _storage = storage ??
            const FlutterSecureStorage(
              aOptions: AndroidOptions(encryptedSharedPreferences: true),
              iOptions: IOSOptions(
                accessibility: KeychainAccessibility.first_unlock,
              ),
              webOptions: WebOptions(dbName: 'jobify_app_secure'),
            );

  final FlutterSecureStorage _storage;

  static const _kRefreshKey = 'jobify.refresh_token';

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _kRefreshKey);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: _kRefreshKey, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _kRefreshKey);
}

@Riverpod(keepAlive: true)
TokenStorage tokenStorage(Ref ref) => SecureTokenStorage();
