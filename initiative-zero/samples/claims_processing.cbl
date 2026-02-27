      * ══════════════════════════════════════════════
      * CLAIMS PROCESSING — CROWN JEWEL SYSTEM
      * Last modified: 1997-03-14 by J. Morrison
      * WARNING: Do not modify CALC-PAYOUT section
      * ══════════════════════════════════════════════
       IDENTIFICATION DIVISION.
       PROGRAM-ID. PROCESS-CLAIM.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-CLAIM-RECORD.
          05 WS-CLAIM-ID          PIC 9(8).
          05 WS-POLICY-NUMBER     PIC X(10).
          05 WS-CLAIM-AMOUNT      PIC 9(7)V99.
          05 WS-DEDUCTIBLE        PIC 9(5)V99.
          05 WS-COVERAGE-LIMIT    PIC 9(7)V99.
          05 WS-APPROVAL-STATUS   PIC X(1).
             88 APPROVED             VALUE 'A'.
             88 DENIED               VALUE 'D'.
             88 PENDING              VALUE 'P'.
       01 WS-PAYOUT-AMOUNT       PIC 9(7)V99.
       01 WS-NET-CLAIM           PIC 9(7)V99.
       01 WS-ERROR-CODE          PIC 9(4).

       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM VALIDATE-CLAIM
           IF WS-ERROR-CODE = 0
              PERFORM CALC-PAYOUT
              PERFORM UPDATE-STATUS
              PERFORM WRITE-AUDIT-LOG
           END-IF
           STOP RUN.

       VALIDATE-CLAIM.
           IF WS-CLAIM-AMOUNT > WS-COVERAGE-LIMIT
              MOVE 1001 TO WS-ERROR-CODE
              SET DENIED TO TRUE
           ELSE IF WS-POLICY-NUMBER = SPACES
              MOVE 1002 TO WS-ERROR-CODE
              SET DENIED TO TRUE
           ELSE
              MOVE 0 TO WS-ERROR-CODE
           END-IF.

       CALC-PAYOUT.
      * CRITICAL: Deductible logic — regulatory
           SUBTRACT WS-DEDUCTIBLE FROM WS-CLAIM-AMOUNT
              GIVING WS-NET-CLAIM
           IF WS-NET-CLAIM > WS-COVERAGE-LIMIT
              MOVE WS-COVERAGE-LIMIT TO WS-PAYOUT-AMOUNT
           ELSE
              MOVE WS-NET-CLAIM TO WS-PAYOUT-AMOUNT
           END-IF
           SET APPROVED TO TRUE.

       UPDATE-STATUS.
           CONTINUE.

       WRITE-AUDIT-LOG.
           CONTINUE.
