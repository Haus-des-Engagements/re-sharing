# 20. File Storage Strategy

Date: 2025-01-20

## Status

Accepted

## Context

The booking platform handles multiple types of files with different access requirements:
* **Resource images**: Public photos of bookable spaces
* **Organization usage agreements**: Private PDF documents requiring access control
* **Static files**: CSS, JavaScript, images for the application itself
* **Media uploads**: User-generated content requiring validation and security

Different file types have different requirements:
* **Public files**: Should be fast to serve, cacheable, and accessible to all users
* **Private files**: Require authentication and time-limited access URLs
* **Static files**: Need efficient serving in production with compression and caching
* **Development**: Local file storage for rapid development without cloud dependencies

We considered the following options for media storage:
1. Local filesystem storage (Django's default)
2. AWS S3 with django-storages
3. Cloudflare R2 or DigitalOcean Spaces (S3-compatible)
4. Self-hosted MinIO (S3-compatible)
5. CDN integration (CloudFront, Cloudflare)

For static files:
1. Nginx serving static files directly
2. WhiteNoise middleware (Python-based static serving)
3. CDN with AWS S3 origin
4. Django's default static file serving (development only)

Key requirements:
* Different security levels for different file types
* Production-ready performance and reliability
* Cost-effective solution for small-scale deployment
* Simple development setup without cloud dependencies
* Future scalability to handle more files
* Backup and disaster recovery capabilities

## Decision

We will implement a **dual-storage strategy** with different configurations for development and production:

### Media File Storage (User Uploads)

**Development:**
* Django's default FileSystemStorage
* Files stored locally in `/mediafiles/` directory
* Fast iteration without cloud setup

**Production:**
* **Default (Public) Storage**: S3-Interface via django-storages[s3]
  * Used for: Resource images, public attachments
  * No authentication required
  * Direct S3 URLs for fast access
  * Bucket configured for public read access

* **Private Storage**: AWS S3-Interface with querystring authentication
  * Used for: Organization usage agreements (PDFs)
  * Presigned URLs with 600-second (10 minute) TTL by default
  * TTL configurable via DJANGO_AWS_QUERYSTRING_EXPIRE setting
  * Access URLs generated on-demand per request
  * Bucket configured to deny public access

### Static File Storage (CSS, JS, Images)

**Development:**
* Django's FileSystemStorage
* Files in `/re_sharing/static/` (source)
* Served via Django development server

**Production:**
* **WhiteNoise** middleware for static file serving
* CompressedManifestStaticFilesStorage for:
  - Automatic Gzip compression
  - Cache-busting via manifest file with content hashes
  - Efficient serving directly from Python application
* Static files collected to `/staticfiles/` directory
* No separate static file CDN (WhiteNoise handles caching headers)

### File Validation

* PDF validation for usage agreements (MIME type checking)
* Image extension validation (.jpg, .jpeg, .png, .gif, .webp)
* File size limits enforced at application level
* Upload path customization based on model instance

### S3 Configuration

* Single S3 bucket with prefix-based organization
* IAM credentials via environment variables
* Configurable S3 endpoint URL (supports S3-compatible services)
* Connection settings:
  - AWS_S3_FILE_OVERWRITE = False (prevent accidental overwrites)
  - AWS_QUERYSTRING_EXPIRE = 600 (10 minutes for private file access)

## Consequences

* **Production dependency on S3-Provider ** - outages affect file access
* **Development is cloud-independent** - no credentials needed locally
* Private files are secure but URLs expire after 10 minutes
* WhiteNoise eliminates need for Nginx configuration for static files
* Static files are served efficiently with proper caching headers
* S3 costs scale with storage and bandwidth usage
* File uploads are auditable via django-auditlog
* Migration between S3-compatible services is possible via endpoint URL config
* No CDN means static files served from application server (acceptable for project scale)
* Backup strategy relies on S3's built-in durability and versioning
* File migrations between environments require S3 sync or manual transfer
* Local development files not committed to git (in .gitignore)
* The dual storage approach adds complexity but provides flexibility
* Presigned URLs provide temporary access without exposing credentials
* WhiteNoise compression reduces bandwidth usage
* Static file manifest enables aggressive browser caching
* File validation prevents malicious uploads
* Custom upload paths improve S3 bucket organization
* The project can switch to Cloudflare R2 or MinIO by changing endpoint URL
* No automatic image optimization or thumbnail generation (future enhancement)
* File deletion from S3 must be handled explicitly (not automatic on model deletion)
* CORS configuration needed if files accessed from different domains
* Private storage access control depends on Django view-level authorization
