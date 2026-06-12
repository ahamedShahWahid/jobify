import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

const _kRequestIdExtraKey = 'jobify.requestId';
const _kRequestIdHeader = 'X-Request-Id';

/// Generates a uuid4 per outgoing request, sets it as X-Request-Id, and
/// stashes it in options.extra so error mapping can attach it to thrown
/// exceptions even when the response has no body.
class RequestIdInterceptor extends Interceptor {
  RequestIdInterceptor({Uuid? uuid}) : _uuid = uuid ?? const Uuid();

  final Uuid _uuid;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    final id = _uuid.v4();
    options.headers[_kRequestIdHeader] = id;
    options.extra[_kRequestIdExtraKey] = id;
    handler.next(options);
  }
}

String? requestIdFromOptions(RequestOptions options) =>
    options.extra[_kRequestIdExtraKey] as String?;
