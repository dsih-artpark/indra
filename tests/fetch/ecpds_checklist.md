### 1. last_date_of_ecpds_data()
- [x] Test HTTP request failure (404)
- [x] Test successful HTTP request with valid data
- [ ] Test HTML parsing edge cases:
  - [x] Empty HTML response
  - [x] Malformed HTML
  - [x] No links present
  - [x] Links without valid dates
  - [x] Links with mixed valid/invalid dates
- [ ] Time-based logic:
  - [x] Current time before 8:49 UTC threshold
  - [x] Current time exactly at 8:49 UTC
  - [x] Current time after 8:49 UTC
  - [ ] Case where previous date isn't in dates list
- [ ] URL handling:
  - [ ] Test with different base_url values
  - [ ] Test with trailing/no trailing slashes

### 2. construct_ecpds_urls()
- [ ] Test basic URL construction
- [ ] Test with various config combinations:
  - [ ] Single format
  - [ ] Multiple formats
  - [ ] Different reference times
  - [ ] Different models
  - [ ] Different resolutions
  - [ ] Different streams
  - [ ] Different steps
  - [ ] Different types
- [ ] Edge cases:
  - [ ] Empty configs list
  - [ ] Missing required config keys
  - [ ] Invalid date format
  - [ ] Base URL variations (with/without trailing slash)

### 3. main() CLI Function
- [ ] Test CLI arguments:
  - [ ] yaml_path validation
  - [ ] get_latest_date flag
  - [ ] custom_date option
  - [ ] upload flag
  - [ ] directory option
- [ ] Test error handling:
  - [ ] Invalid YAML file
  - [ ] Missing required params
  - [ ] S3 upload failures
  - [ ] Directory creation failures
- [ ] Test report generation:
  - [ ] Success scenarios
  - [ ] Error scenarios
  - [ ] Critical failure scenarios
  - [ ] Email attachment logic
- [ ] Test file handling:
  - [ ] Temporary directory creation
  - [ ] Custom directory usage
  - [ ] File download verification
  - [ ] Upload verification

### 4. Integration Tests
- [ ] End-to-end workflow:
  - [ ] Successful download and upload
  - [ ] Partial success scenarios
  - [ ] Complete failure scenarios
- [ ] S3 integration
- [ ] Email reporting integration