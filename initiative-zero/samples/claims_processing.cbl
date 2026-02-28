      * ══════════════════════════════════════════════════════════
      * CLAIMS PROCESSING — CROWN JEWEL SYSTEM
      * Module: PROCESS-CLAIM (Transaction CLM-100)
      * Batch cycle: Nightly 23:30 EST, Freq: Daily
      * Upstream: POLICY-MASTER (DB2 VSAM), CLM-INTAKE-Q
      * Downstream: GL-POSTING, REINSURANCE-FEED, AUDIT-ARCHIVE
      * Last modified: 1997-03-14 by J. Morrison
      * Patch 2001-06-22 K. Patel — Y2K date fix paragraph
      * Patch 2004-09-30 R. Singh — Added fraud hold status
      * Patch 2011-01-15 L. Torres — Regulatory cap override
      * WARNING: Do not modify CALC-PAYOUT section without
      *   sign-off from Compliance (ref: REG-2010-447)
      * WARNING: COPY POLHIST-REC dependency in UPDATE-STATUS
      * ══════════════════════════════════════════════════════════
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROCESS-CLAIM.
       AUTHOR. J. MORRISON.
       DATE-WRITTEN. 1994-08-12.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
      *    SELECT CLAIM-FILE ASSIGN TO 'CLM.DAILY.INPUT'
      *        ORGANIZATION IS SEQUENTIAL
      *        ACCESS MODE IS SEQUENTIAL
      *        FILE STATUS IS WS-FILE-STATUS.
      *    SELECT AUDIT-FILE ASSIGN TO 'CLM.AUDIT.LOG'
      *        ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      * --- COPYBOOK REFERENCES (production includes via COPY) ---
      * COPY POLHIST-REC.   (Policy history record layout)
      * COPY CLMTYPE-TBL.   (Claim type code table)
      * COPY ERRMSG-REC.    (Standardized error messages)
      * COPY AUDITCTL-REC.  (Audit control record)
      * COPY REGCAP-TBL.    (Regulatory cap table by state)

       01 WS-CLAIM-RECORD.
          05 WS-CLAIM-ID          PIC 9(8).
          05 WS-POLICY-NUMBER     PIC X(10).
          05 WS-CLAIM-TYPE        PIC X(3).
             88 MEDICAL              VALUE 'MED'.
             88 DENTAL               VALUE 'DEN'.
             88 VISION               VALUE 'VIS'.
             88 PHARMACY             VALUE 'RXP'.
          05 WS-CLAIM-AMOUNT      PIC 9(7)V99.
          05 WS-DEDUCTIBLE        PIC 9(5)V99.
          05 WS-COVERAGE-LIMIT    PIC 9(7)V99.
          05 WS-COPAY-PCT         PIC 9(2)V99.
          05 WS-APPROVAL-STATUS   PIC X(1).
             88 APPROVED             VALUE 'A'.
             88 DENIED               VALUE 'D'.
             88 PENDING              VALUE 'P'.
             88 FRAUD-HOLD           VALUE 'F'.
             88 MANAGER-REVIEW       VALUE 'M'.
          05 WS-CLAIMANT-STATE    PIC X(2).
          05 WS-PROVIDER-ID       PIC X(12).
          05 WS-SERVICE-DATE      PIC 9(8).
          05 WS-SUBMISSION-DATE   PIC 9(8).

       01 WS-PAYOUT-AMOUNT       PIC 9(7)V99.
       01 WS-NET-CLAIM           PIC 9(7)V99.
       01 WS-COPAY-AMOUNT        PIC 9(7)V99.
       01 WS-ERROR-CODE          PIC 9(4).

      * --- THRESHOLDS AND CONFIGURATION ---
       01 WS-THRESHOLDS.
          05 WS-MANAGER-REVIEW-AMT PIC 9(7)V99 VALUE 50000.00.
          05 WS-FRAUD-SCORE-LIMIT  PIC 9(3)     VALUE 080.
          05 WS-MAX-CLAIM-AGE-DAYS PIC 9(3)     VALUE 180.
          05 WS-REGULATORY-CAP     PIC 9(7)V99 VALUE 99999.99.

      * --- BATCH CONTROL ---
       01 WS-BATCH-CONTROL.
          05 WS-CLAIMS-READ       PIC 9(6)     VALUE 0.
          05 WS-CLAIMS-APPROVED   PIC 9(6)     VALUE 0.
          05 WS-CLAIMS-DENIED     PIC 9(6)     VALUE 0.
          05 WS-CLAIMS-PENDED     PIC 9(6)     VALUE 0.
          05 WS-TOTAL-PAID-AMT    PIC 9(9)V99  VALUE 0.
          05 WS-BATCH-DATE        PIC 9(8).
          05 WS-BATCH-ID          PIC X(12).

      * --- DATE WORK FIELDS ---
       01 WS-DATE-WORK.
          05 WS-CURRENT-DATE      PIC 9(8).
          05 WS-DATE-DIFF-DAYS    PIC 9(5).
          05 WS-FORMATTED-DATE    PIC X(10).
          05 WS-FILE-STATUS       PIC X(2).

      * --- AUDIT TRAIL ---
       01 WS-AUDIT-RECORD.
          05 WA-TIMESTAMP         PIC X(26).
          05 WA-CLAIM-ID          PIC 9(8).
          05 WA-ACTION            PIC X(12).
          05 WA-OPERATOR-ID       PIC X(8).
          05 WA-AMOUNT            PIC 9(7)V99.
          05 WA-REASON-CODE       PIC 9(4).

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM INIT-BATCH
           PERFORM VALIDATE-CLAIM
           IF WS-ERROR-CODE = 0
              PERFORM CHECK-CLAIM-AGE
           END-IF
           IF WS-ERROR-CODE = 0
              PERFORM CALC-PAYOUT
              PERFORM CHECK-MANAGER-THRESHOLD
              PERFORM APPLY-REGULATORY-CAP
              PERFORM UPDATE-STATUS
              PERFORM UPDATE-BATCH-COUNTS
              PERFORM WRITE-AUDIT-LOG
           END-IF
           PERFORM WRITE-BATCH-CONTROL
           STOP RUN.

       INIT-BATCH.
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD
           MOVE WS-CURRENT-DATE TO WS-BATCH-DATE
           ADD 1 TO WS-CLAIMS-READ.

       VALIDATE-CLAIM.
      * BR: Claim amount must not exceed coverage limit
           IF WS-CLAIM-AMOUNT > WS-COVERAGE-LIMIT
              MOVE 1001 TO WS-ERROR-CODE
              SET DENIED TO TRUE
      * BR: Policy number is required — reject if blank
           ELSE IF WS-POLICY-NUMBER = SPACES
              MOVE 1002 TO WS-ERROR-CODE
              SET DENIED TO TRUE
      * BR: Provider ID is required for all claim types
           ELSE IF WS-PROVIDER-ID = SPACES
              MOVE 1003 TO WS-ERROR-CODE
              SET DENIED TO TRUE
      * BR: Service date cannot be in the future
           ELSE IF WS-SERVICE-DATE > WS-CURRENT-DATE
              MOVE 1004 TO WS-ERROR-CODE
              SET DENIED TO TRUE
           ELSE
              MOVE 0 TO WS-ERROR-CODE
           END-IF.

       CHECK-CLAIM-AGE.
      * BR: Claims older than 180 days are auto-denied
      * Patch 2001-06-22 K. Patel — Y2K-safe date calc
           COMPUTE WS-DATE-DIFF-DAYS =
              FUNCTION INTEGER-OF-DATE(WS-CURRENT-DATE)
              - FUNCTION INTEGER-OF-DATE(WS-SERVICE-DATE)
           IF WS-DATE-DIFF-DAYS > WS-MAX-CLAIM-AGE-DAYS
              MOVE 1005 TO WS-ERROR-CODE
              SET DENIED TO TRUE
              MOVE 'CLAIM AGE EXCEEDED' TO WA-ACTION
           END-IF.

       CALC-PAYOUT.
      * CRITICAL: Deductible logic — regulatory requirement
      * Do NOT modify without Compliance sign-off (REG-2010-447)
           SUBTRACT WS-DEDUCTIBLE FROM WS-CLAIM-AMOUNT
              GIVING WS-NET-CLAIM
      * BR: Apply copay percentage after deductible
           IF WS-COPAY-PCT > 0
              MULTIPLY WS-NET-CLAIM BY WS-COPAY-PCT
                 GIVING WS-COPAY-AMOUNT
              DIVIDE WS-COPAY-AMOUNT BY 100
                 GIVING WS-COPAY-AMOUNT
              SUBTRACT WS-COPAY-AMOUNT FROM WS-NET-CLAIM
                 GIVING WS-NET-CLAIM
           END-IF
      * BR: Payout capped at coverage limit
           IF WS-NET-CLAIM > WS-COVERAGE-LIMIT
              MOVE WS-COVERAGE-LIMIT TO WS-PAYOUT-AMOUNT
           ELSE
              MOVE WS-NET-CLAIM TO WS-PAYOUT-AMOUNT
           END-IF
           SET APPROVED TO TRUE.

       CHECK-MANAGER-THRESHOLD.
      * BR: Claims above $50,000 require manager review
      * Patch 2004-09-30 R. Singh — Added fraud hold pathway
           IF WS-PAYOUT-AMOUNT > WS-MANAGER-REVIEW-AMT
              SET MANAGER-REVIEW TO TRUE
              MOVE 'MANAGER REVIEW REQUIRED' TO WA-ACTION
              ADD 1 TO WS-CLAIMS-PENDED
           END-IF.

       APPLY-REGULATORY-CAP.
      * BR: State-level regulatory cap on single claim payout
      * Patch 2011-01-15 L. Torres — Regulatory cap override
      *   Previously hardcoded; now reads from REGCAP-TBL
      *   (Demo: uses default WS-REGULATORY-CAP value)
           IF WS-PAYOUT-AMOUNT > WS-REGULATORY-CAP
              MOVE WS-REGULATORY-CAP TO WS-PAYOUT-AMOUNT
              MOVE 'REGULATORY CAP APPLIED' TO WA-ACTION
           END-IF.

       UPDATE-STATUS.
      * NOTE: Production reads POLHIST-REC via COPY statement
      *   to update policy claim history counters.
      *   Demo version: status update only.
           CONTINUE.

       UPDATE-BATCH-COUNTS.
           IF APPROVED
              ADD 1 TO WS-CLAIMS-APPROVED
              ADD WS-PAYOUT-AMOUNT TO WS-TOTAL-PAID-AMT
           ELSE IF DENIED
              ADD 1 TO WS-CLAIMS-DENIED
           ELSE
              ADD 1 TO WS-CLAIMS-PENDED
           END-IF.

       WRITE-AUDIT-LOG.
      * BR: Every claim decision must be logged for compliance
           MOVE WS-CLAIM-ID TO WA-CLAIM-ID
           MOVE WS-PAYOUT-AMOUNT TO WA-AMOUNT
           MOVE WS-ERROR-CODE TO WA-REASON-CODE
           CONTINUE.

       WRITE-BATCH-CONTROL.
      * End-of-batch summary for reconciliation
           CONTINUE.
