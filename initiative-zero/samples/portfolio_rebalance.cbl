      * ══════════════════════════════════════════════════════════
      * PORTFOLIO REBALANCING ENGINE
      * Module: REBAL-ENGINE (Batch Job WRBAL-100)
      * Wealth Management — Core System
      * Batch cycle: Nightly 02:00 EST
      * Upstream: POSITION-MASTER, PRICE-FEED, ACCT-PROFILE
      * Downstream: ORDER-MGMT-Q, TAX-LOT-LEDGER, COMPLIANCE-RPT
      * Last modified: 2004-11-22 by R. Takahashi
      * Patch 2008-03-15 M. Johnson — Added concentrated
      *   position check per SEC Rule 144 guidance
      * Patch 2012-07-01 A. Nakamura — Fee breakeven logic
      * Patch 2016-11-30 S. Williams — Lot-size rounding
      * WARNING: WASH-SALE-CHECK interacts with TAX-LOT
      *   subsystem via COPY TAXLOT-REC. Do not modify
      *   independently.
      * WARNING: CALC-TRADE precision must match ORDER-MGMT
      *   decimal format (9(9)V99) — truncation causes
      *   reconciliation breaks if changed.
      * ══════════════════════════════════════════════════════════
       IDENTIFICATION DIVISION.
       PROGRAM-ID. REBAL-ENGINE.
       AUTHOR. R. TAKAHASHI.
       DATE-WRITTEN. 2002-05-18.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
      *    SELECT POSITION-FILE ASSIGN TO 'WM.POS.MASTER'
      *        ORGANIZATION IS INDEXED
      *        ACCESS MODE IS DYNAMIC
      *        RECORD KEY IS WS-ACCOUNT-ID
      *        FILE STATUS IS WS-FILE-STATUS.
      *    SELECT TRADE-OUTQ ASSIGN TO 'WM.TRADE.OUTQ'
      *        ORGANIZATION IS SEQUENTIAL.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      * --- COPYBOOK REFERENCES ---
      * COPY TAXLOT-REC.    (Tax lot record — wash sale data)
      * COPY ACCTPROF-REC.  (Account profile — risk tolerance)
      * COPY PRICEFEED-REC. (Real-time pricing record)
      * COPY FEETABLE-REC.  (Commission and fee schedule)
      * COPY REBALCTL-REC.  (Rebalance control parameters)

       01 WS-PORTFOLIO-REC.
          05 WS-ACCOUNT-ID        PIC X(12).
          05 WS-ASSET-CLASS       PIC X(4).
             88 EQUITY               VALUE 'EQTY'.
             88 FIXED-INCOME         VALUE 'FIXD'.
             88 CASH                 VALUE 'CASH'.
             88 ALTERNATIVES         VALUE 'ALTS'.
          05 WS-TARGET-ALLOC      PIC 9(3)V99.
          05 WS-CURRENT-ALLOC     PIC 9(3)V99.
          05 WS-DRIFT-PCT         PIC S9(3)V99.
          05 WS-MARKET-VALUE      PIC 9(9)V99.
          05 WS-UNREALIZED-GL     PIC S9(9)V99.
          05 WS-HOLD-DAYS         PIC 9(5).
          05 WS-COST-BASIS        PIC 9(9)V99.
          05 WS-POSITION-PCT      PIC 9(3)V99.
          05 WS-REBAL-ACTION      PIC X(4).
             88 BUY-ORDER            VALUE 'BUY '.
             88 SELL-ORDER           VALUE 'SELL'.
             88 HOLD-ORDER           VALUE 'HOLD'.
          05 WS-TRADE-AMOUNT      PIC 9(9)V99.
          05 WS-SYMBOL            PIC X(8).

      * --- THRESHOLDS AND CONFIGURATION ---
       01 WS-THRESHOLDS.
          05 WS-DRIFT-TRIGGER     PIC 9(3)V99 VALUE 5.00.
          05 WS-MIN-TRADE         PIC 9(7)V99 VALUE 50.00.
          05 WS-TLH-THRESHOLD     PIC S9(9)V99 VALUE -3000.00.
          05 WS-WASH-SALE-DAYS    PIC 9(3)     VALUE 030.
          05 WS-CONCENTRATED-PCT  PIC 9(3)V99 VALUE 25.00.
          05 WS-LOT-SIZE          PIC 9(5)     VALUE 00001.
          05 WS-TRADE-FEE-FLAT    PIC 9(5)V99 VALUE 9.95.
          05 WS-FEE-BREAKEVEN-MIN PIC 9(7)V99 VALUE 100.00.

      * --- ASSET-CLASS SPECIFIC DRIFT THRESHOLDS ---
      * Patch 2008-03-15 — Different classes tolerate
      *   different drift bands before triggering rebalance
       01 WS-CLASS-THRESHOLDS.
          05 WS-EQUITY-DRIFT-TRIGGER  PIC 9(3)V99 VALUE 5.00.
          05 WS-FIXED-DRIFT-TRIGGER   PIC 9(3)V99 VALUE 3.00.
          05 WS-CASH-DRIFT-TRIGGER    PIC 9(3)V99 VALUE 2.00.
          05 WS-ALTS-DRIFT-TRIGGER    PIC 9(3)V99 VALUE 7.00.

      * --- WORK FIELDS ---
       01 WS-WORK-FIELDS.
          05 WS-ABS-DRIFT         PIC 9(3)V99.
          05 WS-EFFECTIVE-TRIGGER PIC 9(3)V99.
          05 WS-GROSS-TRADE       PIC 9(9)V99.
          05 WS-NET-TRADE         PIC 9(9)V99.
          05 WS-TRADE-FEE         PIC 9(5)V99.
          05 WS-FILE-STATUS       PIC X(2).

       01 WS-REBAL-FLAG           PIC X(1).
          88 REBAL-NEEDED            VALUE 'Y'.
          88 REBAL-SKIP              VALUE 'N'.
       01 WS-TLH-FLAG             PIC X(1).
          88 TLH-TRIGGERED           VALUE 'Y'.
          88 TLH-SKIP                VALUE 'N'.
       01 WS-CONCENTRATED-FLAG    PIC X(1).
          88 CONCENTRATED-POS        VALUE 'Y'.
          88 NORMAL-POS              VALUE 'N'.
       01 WS-ERROR-CODE           PIC 9(4).
       01 WS-AUDIT-REASON         PIC X(40).

      * --- BATCH CONTROL ---
       01 WS-BATCH-CONTROL.
          05 WB-ACCOUNTS-READ     PIC 9(6) VALUE 0.
          05 WB-TRADES-GENERATED  PIC 9(6) VALUE 0.
          05 WB-TRADES-BLOCKED    PIC 9(6) VALUE 0.
          05 WB-HOLDS-COUNT       PIC 9(6) VALUE 0.
          05 WB-TLH-COUNT         PIC 9(6) VALUE 0.
          05 WB-TOTAL-TRADE-AMT   PIC 9(11)V99 VALUE 0.
          05 WB-BATCH-DATE        PIC 9(8).
          05 WB-BATCH-ID          PIC X(12).

      * --- AUDIT TRAIL ---
       01 WS-AUDIT-RECORD.
          05 WA-TIMESTAMP         PIC X(26).
          05 WA-ACCOUNT-ID        PIC X(12).
          05 WA-ACTION            PIC X(4).
          05 WA-AMOUNT            PIC 9(9)V99.
          05 WA-REASON            PIC X(40).
          05 WA-TLH-FLAG          PIC X(1).
          05 WA-COMPLIANCE-REF    PIC X(16).

       PROCEDURE DIVISION.
       MAIN-REBALANCE.
           PERFORM INIT-REBAL-BATCH
           PERFORM CALC-DRIFT
           PERFORM SET-CLASS-THRESHOLD
           PERFORM CHECK-REBAL-TRIGGER
           IF REBAL-NEEDED
              PERFORM CHECK-CONCENTRATED-POSITION
              PERFORM CHECK-TAX-LOSS-HARVEST
              PERFORM CHECK-WASH-SALE
              PERFORM CALC-TRADE
              PERFORM APPLY-LOT-ROUNDING
              PERFORM CALC-TRADE-FEE
              PERFORM VALIDATE-FEE-BREAKEVEN
              PERFORM VALIDATE-MIN-TRADE
              PERFORM UPDATE-BATCH-COUNTS
              PERFORM WRITE-REBAL-AUDIT
           ELSE
              SET HOLD-ORDER TO TRUE
              MOVE 'DRIFT WITHIN THRESHOLD' TO WS-AUDIT-REASON
              ADD 1 TO WB-HOLDS-COUNT
              PERFORM WRITE-REBAL-AUDIT
           END-IF
           PERFORM WRITE-BATCH-SUMMARY
           STOP RUN.

       INIT-REBAL-BATCH.
           ACCEPT WB-BATCH-DATE FROM DATE YYYYMMDD
           ADD 1 TO WB-ACCOUNTS-READ.

       CALC-DRIFT.
      * BR: Drift = current allocation minus target allocation
           SUBTRACT WS-TARGET-ALLOC FROM WS-CURRENT-ALLOC
              GIVING WS-DRIFT-PCT.

       SET-CLASS-THRESHOLD.
      * BR: Each asset class has its own drift trigger threshold
      * Patch 2008-03-15 M. Johnson — Class-specific thresholds
           EVALUATE TRUE
              WHEN EQUITY
                 MOVE WS-EQUITY-DRIFT-TRIGGER
                    TO WS-EFFECTIVE-TRIGGER
              WHEN FIXED-INCOME
                 MOVE WS-FIXED-DRIFT-TRIGGER
                    TO WS-EFFECTIVE-TRIGGER
              WHEN CASH
                 MOVE WS-CASH-DRIFT-TRIGGER
                    TO WS-EFFECTIVE-TRIGGER
              WHEN ALTERNATIVES
                 MOVE WS-ALTS-DRIFT-TRIGGER
                    TO WS-EFFECTIVE-TRIGGER
              WHEN OTHER
                 MOVE WS-DRIFT-TRIGGER
                    TO WS-EFFECTIVE-TRIGGER
           END-EVALUATE.

       CHECK-REBAL-TRIGGER.
      * BR: Rebalance only if absolute drift > class threshold
           COMPUTE WS-ABS-DRIFT =
              FUNCTION ABS(WS-DRIFT-PCT)
           IF WS-ABS-DRIFT > WS-EFFECTIVE-TRIGGER
              SET REBAL-NEEDED TO TRUE
           ELSE
              SET REBAL-SKIP TO TRUE
           END-IF.

       CHECK-CONCENTRATED-POSITION.
      * BR: Flag positions exceeding 25% of portfolio
      * Regulatory guidance: SEC Rule 144 concentration limits
      * Patch 2008-03-15 M. Johnson
           IF WS-POSITION-PCT > WS-CONCENTRATED-PCT
              SET CONCENTRATED-POS TO TRUE
              MOVE 'CONCENTRATED POSITION FLAG'
                 TO WS-AUDIT-REASON
           ELSE
              SET NORMAL-POS TO TRUE
           END-IF.

       CHECK-TAX-LOSS-HARVEST.
      * BR: If unrealized loss exceeds TLH threshold,
      *     flag for tax-loss harvesting opportunity
           IF WS-UNREALIZED-GL < WS-TLH-THRESHOLD
              SET TLH-TRIGGERED TO TRUE
              MOVE 'TLH OPPORTUNITY DETECTED' TO
                 WS-AUDIT-REASON
              ADD 1 TO WB-TLH-COUNT
           ELSE
              SET TLH-SKIP TO TRUE
           END-IF.

       CHECK-WASH-SALE.
      * BR: Block sale if position held < 30 days
      *     to avoid wash sale violation (IRS Rule)
           IF WS-HOLD-DAYS < WS-WASH-SALE-DAYS
              SET HOLD-ORDER TO TRUE
              SET REBAL-SKIP TO TRUE
              MOVE 'WASH SALE BLOCK' TO WS-AUDIT-REASON
              MOVE 2001 TO WS-ERROR-CODE
              ADD 1 TO WB-TRADES-BLOCKED
           END-IF.

       CALC-TRADE.
      * BR: Trade amount = market_value * abs(drift_pct) / 100
      *     Direction based on sign of drift
      * WARNING: Precision must match ORDER-MGMT format
           MULTIPLY WS-MARKET-VALUE BY WS-ABS-DRIFT
              GIVING WS-GROSS-TRADE
           DIVIDE WS-GROSS-TRADE BY 100
              GIVING WS-GROSS-TRADE
           MOVE WS-GROSS-TRADE TO WS-TRADE-AMOUNT
           IF WS-DRIFT-PCT > 0
              SET SELL-ORDER TO TRUE
           ELSE
              SET BUY-ORDER TO TRUE
           END-IF.

       APPLY-LOT-ROUNDING.
      * BR: Round trade to nearest whole lot size
      * Patch 2016-11-30 S. Williams
      * NOTE: Currently lot size = 1 (single shares).
      *   Some fixed-income products use lot size = 1000.
           IF WS-LOT-SIZE > 1
              DIVIDE WS-TRADE-AMOUNT BY WS-LOT-SIZE
                 GIVING WS-TRADE-AMOUNT ROUNDED
              MULTIPLY WS-TRADE-AMOUNT BY WS-LOT-SIZE
                 GIVING WS-TRADE-AMOUNT
           END-IF.

       CALC-TRADE-FEE.
      * BR: Apply flat transaction fee per trade
      * Patch 2012-07-01 A. Nakamura
           MOVE WS-TRADE-FEE-FLAT TO WS-TRADE-FEE.

       VALIDATE-FEE-BREAKEVEN.
      * BR: Skip trade if fee exceeds 10% of trade value
      *     (fee erosion protection)
      * Patch 2012-07-01 A. Nakamura
           IF WS-TRADE-AMOUNT < WS-FEE-BREAKEVEN-MIN
              SET HOLD-ORDER TO TRUE
              SET REBAL-SKIP TO TRUE
              MOVE 'BELOW FEE BREAKEVEN' TO WS-AUDIT-REASON
              ADD 1 TO WB-TRADES-BLOCKED
           END-IF.

       VALIDATE-MIN-TRADE.
      * BR: Skip if trade below $50 minimum — fee erosion
           IF WS-TRADE-AMOUNT < WS-MIN-TRADE
              SET HOLD-ORDER TO TRUE
              SET REBAL-SKIP TO TRUE
              MOVE 'BELOW MIN TRADE THRESHOLD'
                 TO WS-AUDIT-REASON
              ADD 1 TO WB-TRADES-BLOCKED
           END-IF.

       UPDATE-BATCH-COUNTS.
           IF NOT HOLD-ORDER
              ADD 1 TO WB-TRADES-GENERATED
              ADD WS-TRADE-AMOUNT TO WB-TOTAL-TRADE-AMT
           END-IF.

       WRITE-REBAL-AUDIT.
      * BR: Every rebalance decision logged for compliance
           MOVE WS-ACCOUNT-ID TO WA-ACCOUNT-ID
           MOVE WS-REBAL-ACTION TO WA-ACTION
           MOVE WS-TRADE-AMOUNT TO WA-AMOUNT
           MOVE WS-AUDIT-REASON TO WA-REASON
           MOVE WS-TLH-FLAG TO WA-TLH-FLAG
           CONTINUE.

       WRITE-BATCH-SUMMARY.
      * End-of-batch reconciliation record
           CONTINUE.
