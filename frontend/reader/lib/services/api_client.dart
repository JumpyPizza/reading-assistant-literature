import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../models.dart';

const String apiBaseUrl = 'http://localhost:8000'; // update if needed

class ApiClient {
  const ApiClient();

  Uri _uri(String path, [Map<String, String>? params]) =>
      Uri.parse('$apiBaseUrl$path').replace(queryParameters: params);

  Future<List<BookMeta>> listBooks() async {
    final resp = await http.get(_uri('/documents'));
    if (resp.statusCode != 200) {
      throw Exception('Failed to list books: ${resp.statusCode}');
    }
    final data = json.decode(resp.body) as List<dynamic>;
    return data.map((e) => BookMeta.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<Map<String, String>> uploadDocument({
    required Uint8List bytes,
    required String filename,
    required String title,
  }) async {
    final request = http.MultipartRequest('POST', _uri('/documents/upload'))
      ..fields['title'] = title
      ..fields['author'] = ''
      ..fields['language'] = 'en'
      ..fields['perform_ocr'] = 'false'
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename, contentType: null));
    final streamed = await request.send();
    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) {
      throw Exception('Upload failed (${streamed.statusCode}): $body');
    }
    final data = json.decode(body) as Map<String, dynamic>;
    final bookId = data['book_id'] as String? ?? '';
    final jobId = data['job_id'] as String? ?? '';
    if (bookId.isEmpty || jobId.isEmpty) {
      throw Exception('Upload response missing book_id/job_id');
    }
    return {"book_id": bookId, "job_id": jobId};
  }

  Future<JobStatus> getJob(String jobId) async {
    final resp = await http.get(_uri('/jobs/$jobId'));
    if (resp.statusCode != 200) {
      throw Exception('Job fetch failed: ${resp.statusCode}');
    }
    final data = json.decode(resp.body) as Map<String, dynamic>;
    return JobStatus.fromJson(data);
  }

  Future<void> cancelJob(String jobId) async {
    final resp = await http.post(_uri('/jobs/$jobId/cancel'));
    if (resp.statusCode != 200) {
      throw Exception('Cancel failed: ${resp.statusCode}');
    }
  }

  Future<BookMeta> getBook(String bookId) async {
    final resp = await http.get(_uri('/documents/$bookId'));
    if (resp.statusCode != 200) {
      throw Exception('Book fetch failed: ${resp.statusCode}');
    }
    return BookMeta.fromJson(json.decode(resp.body) as Map<String, dynamic>);
  }

  Future<PageData> fetchParsedPage(String bookId, int page) async {
    final resp = await http.get(_uri('/documents/$bookId/pages/$page/parsed'));
    if (resp.statusCode != 200) {
      throw Exception('Failed to load parsed page: ${resp.statusCode}');
    }
    return PageData.fromJson(json.decode(resp.body) as Map<String, dynamic>);
  }

  String pageImageUrl(String bookId, int page) =>
      '$apiBaseUrl/documents/$bookId/pages/$page/image';
}
