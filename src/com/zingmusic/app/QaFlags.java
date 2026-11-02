package com.zingmusic.app;
// QA/test hook gate. Release builds (build.yml) compile with QA_ENABLED=false,
// which disables the qa_url launch extra and all fixture logging.
final class QaFlags { static final boolean QA_ENABLED = false; }
