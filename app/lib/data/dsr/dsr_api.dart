import 'package:dio/dio.dart';

import 'package:jobify_app/data/dsr/dsr_dto.dart';

class DsrApi {
  DsrApi(this._dio);
  final Dio _dio;

  /// Returns the export envelope as a raw JSON string. We don't parse
  /// Dart-side — the contract is "give me the JSON" — we just relay it
  /// to the clipboard.
  Future<String> exportData() async {
    final res = await _dio.post<dynamic>(
      '/v1/me/dsr/export',
      options: Options(responseType: ResponseType.plain),
    );
    return res.data as String;
  }

  Future<DsrDeleteResponse> deleteAccount() async {
    final res = await _dio.delete<Map<String, dynamic>>(
      '/v1/me/dsr',
      data: {'confirmation': 'DELETE_MY_ACCOUNT'},
    );
    return DsrDeleteResponse.fromJson(res.data!);
  }
}
