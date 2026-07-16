import time
from flask import Flask, request, jsonify
from config import HOST, PORT, DEBUG
from models import AnalyzeRequest, AnalyzeResponse
from analyzer import ReviewAnalyzer
from processor import AnalysisProcessor
from report_generator import ReportGenerator
from logger import api_logger
from exceptions import APIException, BadRequestError, InvalidFormatError
from validation import (
    validate_json_format,
    validate_reviews,
    validate_csv_file
)

app = Flask(__name__)


@app.route("/analyze", methods=["POST"])
def analyze():
    """
    Analyze reviews from JSON or CSV input.

    JSON format: {"reviews": ["review1", "review2", ...]}
    CSV format: multipart/form-data with 'file' parameter (CSV with 'review' column)

    Returns:
        JSON: Analysis results with sentiment, issues, and recommendations
        On error: JSON with error details and status code
    """
    request_start = time.time()
    request_id = f"{request_start}"

    try:
        api_logger.info(f"[{request_id}] Received POST /analyze request")

        reviews = None

        # Handle JSON input
        if request.is_json:
            api_logger.debug(f"[{request_id}] Processing JSON request")
            data = request.get_json()

            try:
                validate_json_format(data)
                reviews = validate_reviews(data.get("reviews", []))
            except APIException as e:
                api_logger.warning(
                    f"[{request_id}] Validation error: {e.error} - {e.detail}"
                )
                return jsonify(e.to_dict()), e.status_code

        # Handle CSV file upload
        elif "file" in request.files:
            api_logger.debug(f"[{request_id}] Processing CSV file upload")
            file = request.files["file"]

            try:
                validate_csv_file(file.filename)
                file_bytes = file.read()

                # Import here to avoid circular dependency
                from input_handler import load_reviews_from_csv

                reviews = load_reviews_from_csv(file_bytes)
            except APIException as e:
                api_logger.warning(
                    f"[{request_id}] CSV validation error: {e.error} - {e.detail}"
                )
                return jsonify(e.to_dict()), e.status_code
            except Exception as e:
                api_logger.error(f"[{request_id}] CSV parsing error: {str(e)}")
                return jsonify(BadRequestError(
                    detail=f"Failed to parse CSV file: {str(e)}"
                ).to_dict()), 400

        else:
            api_logger.warning(f"[{request_id}] No JSON data or CSV file provided")
            return jsonify(BadRequestError(
                detail="Provide JSON data or CSV file. JSON format: {\"reviews\": [...]} or use 'file' parameter for CSV."
            ).to_dict()), 400

        # Perform analysis through full pipeline
        api_logger.info(f"[{request_id}] Starting review analysis with {len(reviews)} reviews")

        try:
            # Step 1: Analyzer - call Claude API
            api_logger.debug(f"[{request_id}] Step 1: Analyzer")
            analyzer = ReviewAnalyzer()
            claude_response = analyzer.analyze_reviews(reviews)

            # Step 2: Processor - process Claude response
            api_logger.debug(f"[{request_id}] Step 2: Processor")
            processor = AnalysisProcessor()
            processed_analysis = processor.process(claude_response, reviews)

            # Step 3: Report Generator - generate final report
            api_logger.debug(f"[{request_id}] Step 3: Report Generator")
            elapsed = time.time() - request_start
            report_generator = ReportGenerator()
            final_report = report_generator.generate(processed_analysis, elapsed)

            api_logger.info(
                f"[{request_id}] Analysis completed successfully in {elapsed:.2f}s"
            )

            return jsonify(final_report), 200

        except APIException as e:
            elapsed = time.time() - request_start
            api_logger.error(
                f"[{request_id}] Analysis failed ({elapsed:.2f}s): {e.error} - {e.detail}"
            )
            return jsonify(e.to_dict()), e.status_code

    except Exception as e:
        elapsed = time.time() - request_start
        api_logger.error(
            f"[{request_id}] Unexpected error ({elapsed:.2f}s): {type(e).__name__} - {str(e)}"
        )
        error_response = {
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred. Please contact support.",
            "status_code": 500
        }
        return jsonify(error_response), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    api_logger.debug("Health check requested")
    return jsonify({"status": "healthy"}), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    api_logger.warning(f"404 Not Found: {request.path}")
    return jsonify({
        "error": "Not Found",
        "detail": f"Endpoint {request.path} does not exist. Use POST /analyze for reviews analysis.",
        "status_code": 404
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors"""
    api_logger.warning(f"405 Method Not Allowed: {request.method} {request.path}")
    return jsonify({
        "error": "Method Not Allowed",
        "detail": f"Method {request.method} is not allowed for {request.path}. Use POST.",
        "status_code": 405
    }), 405


if __name__ == "__main__":
    api_logger.info(f"Starting API server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=DEBUG)
